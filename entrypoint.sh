#!/usr/bin/env bash
set -euo pipefail

: "${FABRIC_CLIENT_ID:?Missing FABRIC_CLIENT_ID}"
: "${FABRIC_CLIENT_SECRET:?Missing FABRIC_CLIENT_SECRET}"
: "${FABRIC_TENANT_ID:?Missing FABRIC_TENANT_ID}"

fab config set encryption_fallback_enabled true   

fab auth login -u "$FABRIC_CLIENT_ID" -p "$FABRIC_CLIENT_SECRET" --tenant "$FABRIC_TENANT_ID"

fab --version

exec python /app/deploy.py "$@"