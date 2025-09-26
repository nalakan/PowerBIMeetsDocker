
import argparse
import os
import sys
import time
import shlex
import subprocess
import requests
from typing import Optional, Dict, Any, List

# -------------------------
# Fabric CLI helpers
# -------------------------
def run_cli(*args: str) -> str:
    cmd = ["fab"] + list(args)
    print(f"[DEBUG] Running: {' '.join(shlex.quote(str(a)) for a in cmd)}")
    res = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if res.stdout:
        print("\n[DEBUG][STDOUT]:\n", res.stdout)
    if res.stderr:
        print("\n[DEBUG][STDERR]:\n", res.stderr)
    if res.returncode != 0:
        print(f"\n[FATAL] fab {' '.join(args)} failed with code {res.returncode}.")
        sys.exit(res.returncode)
    return res.stdout

def copy_item(source_ws: str, item_name: str, item_type: str, target_ws: str, new_name: str, force: bool = True) -> None:
    """
    item_type: 'SemanticModel' or 'Report'
    """
    src = f"{source_ws}.Workspace/{item_name}.{item_type}"
    dest = f"{target_ws}.Workspace/{new_name}.{item_type}"
    cmd = ["cp", src, dest]
    if force:
        cmd.append("-f")
    print(f"[INFO] Copying '{src}' → '{dest}'...")
    run_cli(*cmd)

# -------------------------
# Auth (Power BI REST)
# -------------------------
def get_access_token() -> str:
    tenant_id = os.environ["FABRIC_TENANT_ID"]
    client_id = os.environ["FABRIC_CLIENT_ID"]
    client_secret = os.environ["FABRIC_CLIENT_SECRET"]

    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://analysis.windows.net/powerbi/api/.default",
    }
    resp = requests.post(url, data=data, timeout=60)
    resp.raise_for_status()
    token = resp.json()["access_token"]
    return token

def pbi_get(token: str, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, params=params, timeout=60)
    if resp.status_code == 429:
        retry = int(resp.headers.get("Retry-After", "5"))
        print(f"[WARN] 429 from Power BI API. Retrying after {retry}s...")
        time.sleep(retry)
        resp = requests.get(url, headers=headers, params=params, timeout=60)
    if resp.status_code >= 400:
        print(f"[ERROR] GET {url} failed: {resp.status_code} {resp.text}")
        resp.raise_for_status()
    return resp.json()

def pbi_post(token: str, url: str, json_body: Dict[str, Any]) -> requests.Response:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json=json_body, timeout=60)
    return resp

# -------------------------
# Power BI object lookups
# -------------------------
def get_workspace_id_by_name(token: str, workspace_name: str) -> str:
    """
    Uses Power BI 'groups' endpoint to resolve workspace ID by name.
    """
    url = "https://api.powerbi.com/v1.0/myorg/groups"
    # Pull a lot to avoid paging in most tenants; add paging if needed
    payload = {"$top": 5000}
    data = pbi_get(token, url, payload)
    matches = [g for g in data.get("value", []) if g.get("name") == workspace_name]
    if not matches:
        # Fallback to case-insensitive match
        matches = [g for g in data.get("value", []) if str(g.get("name", "")).lower() == workspace_name.lower()]
    if not matches:
        print(f"[ERROR] Workspace '{workspace_name}' not found via Power BI REST.")
        sys.exit(1)
    if len(matches) > 1:
        print(f"[WARN] Multiple workspaces named '{workspace_name}'. Picking the first. IDs: {[m.get('id') for m in matches]}")
    ws_id = matches[0]["id"]
    print(f"[INFO] Workspace '{workspace_name}' → {ws_id}")
    return ws_id

def get_report_id_by_name(token: str, workspace_id: str, report_name: str) -> str:
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports"
    data = pbi_get(token, url)
    # exact, then case-insensitive
    value = data.get("value", [])
    for r in value:
        if r.get("name") == report_name:
            print(f"[INFO] Report '{report_name}' → {r['id']}")
            return r["id"]
    for r in value:
        if str(r.get("name", "")).lower() == report_name.lower():
            print(f"[INFO] Report (ci) '{report_name}' → {r['id']}")
            return r["id"]
    print(f"[ERROR] Report '{report_name}' not found in workspace {workspace_id}")
    sys.exit(1)

def get_dataset_id_by_name(token: str, workspace_id: str, dataset_name: str) -> str:
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets"
    data = pbi_get(token, url)
    value = data.get("value", [])
    for d in value:
        if d.get("name") == dataset_name:
            print(f"[INFO] Dataset '{dataset_name}' → {d['id']}")
            return d["id"]
    for d in value:
        if str(d.get("name", "")).lower() == dataset_name.lower():
            print(f"[INFO] Dataset (ci) '{dataset_name}' → {d['id']}")
            return d["id"]
    print(f"[ERROR] Dataset '{dataset_name}' not found in workspace {workspace_id}")
    sys.exit(1)

# -------------------------
# Rebind
# -------------------------
def rebind_report(token: str, workspace_id: str, report_id: str, dataset_id: str) -> None:
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports/{report_id}/Rebind"
    body = {"datasetId": dataset_id}
    print(f"[INFO] Rebinding report {report_id} → dataset {dataset_id} (ws {workspace_id})")
    resp = pbi_post(token, url, body)
    if resp.status_code == 200:
        print("[DONE] Report successfully rebound.")
    else:
        print(f"[ERROR] Rebind failed: {resp.status_code} {resp.text}")
        sys.exit(1)

# -------------------------
# Small retry helper (items may take a moment to show up after copy)
# -------------------------
def retry_find(func, tries: int = 12, delay_sec: float = 5.0, *args, **kwargs) -> str:
    last_err: Optional[Exception] = None
    for attempt in range(1, tries + 1):
        try:
            return func(*args, **kwargs)
        except SystemExit as e:
            # Re-raise immediately (explicit fatal)
            raise
        except Exception as e:
            last_err = e
            print(f"[WARN] Attempt {attempt}/{tries} failed: {e}. Retrying in {delay_sec}s...")
            time.sleep(delay_sec)
    print(f"[ERROR] Exhausted retries. Last error: {last_err}")
    sys.exit(1)

# -------------------------
# Main
# -------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-workspace", required=True)
    parser.add_argument("--target-workspace", required=True)
    parser.add_argument("--report-name", required=True)
    parser.add_argument("--semantic-model-name", required=True)
    parser.add_argument("--prefix", required=True, help="Prefix for new report and semantic model, e.g. dev- or Dev-")
    args = parser.parse_args()

    new_report = args.prefix + args.report_name
    new_model  = args.prefix + args.semantic_model_name

    # 1) Copy items (Fabric CLI)
    copy_item(args.source_workspace, args.semantic_model_name, "SemanticModel", args.target_workspace, new_model)
    copy_item(args.source_workspace, args.report_name,         "Report",        args.target_workspace, new_report)

    # 2) Resolve IDs via Power BI REST
    token = get_access_token()

    # Workspace ID by name
    ws_id = get_workspace_id_by_name(token, args.target_workspace)

    # Reports/Datasets sometimes take a few seconds to appear after copy
    dataset_id = retry_find(get_dataset_id_by_name, token=token, workspace_id=ws_id, dataset_name=new_model)
    report_id  = retry_find(get_report_id_by_name,  token=token, workspace_id=ws_id, report_name=new_report)

    # 3) Rebind
    rebind_report(token, ws_id, report_id, dataset_id)

    print("[DONE] Copy and rebind complete.")

if __name__ == "__main__":
    main()
