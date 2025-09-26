# Power BI/Fabric Blue-Green Deployment Tool

## Overview
Automated deployment container for Microsoft Fabric/Power BI reports and semantic models using blue-green deployment strategy. This tool copies reports and models between workspaces and rebinds them automatically using the Fabric CLI and Power BI REST APIs.

## 🏗️ Complete Deployment Flow

```
## Docker Image Build Process
----------------------------
Code Changes (main branch)
        ↓
Azure DevOps Build Pipeline (build-image.yml)
        ↓
Push to Docker Hub Repository
        ↓
Docker Image Available: nalakan/pbi_blue_green_dep_v1:latest

## Deployment (manual) → Pull-once → Containers
-------------------------------------------
Manual Trigger (deploy-image.yml)
        ↓
Image Deployment via DevOps Pipeline
        └─ uses DevOps Variable Libraries (ServicePrincipal, Deployment settings)
        ↓
Pull Image Once (from Docker Hub)   <-- (single pull / staging host)
        ↓
        ├─> docker run --rm <image>  (Container 1)  --> Dev deploy
        ├─> docker run --rm <image>  (Container 2)  --> Test deploy
        └─> docker run --rm <image>  (Container 3)  --> Prod_New deploy

Note: “Pull Image Once” means the pipeline pulls the image (or pulls into host) then runs three ephemeral containers from that image. 
Each container receives its target prefix and workspace settings from the DevOps variable library.

## Expanded step-by-step Process
-----------------------------
1) Build Phase
   - Repo Code Changes  -> Azure DevOps Build Pipeline (build-image.yml)
   - Build pushes image -> Docker Hub (nalakan/pbi_blue_green_dep_v1:latest)

2) Deploy Phase (manual)
   - Manual Trigger -> Image Deployment pipeline (deploy-image.yml)
   - Pipeline reads DevOps Variable Libraries (ServicePrincipal, prefixes, target workspace names)
   - Pipeline pulls Docker image once (or on the host) -> "Pull Image Once"

3) Run Containers (parallel / sequential as pipeline configured)
   - Container 1: docker run --rm <image> --prefix Dev- --target-workspace Dev
       • Auth (Fabric CLI) using ServicePrincipal from DevOps variables
       • Copy Semantic Models from Production Workspace -> Target (Dev-prefixed)
       • Copy Reports -> Target (Dev-prefixed)
       • Rebind Reports to new models (Power BI API)
       • Exit → container removed (because of --rm)

   - Container 2: docker run --rm <image> --prefix Test- --target-workspace Test
       • Auth + Copy + Rebind (prefix Test-)
       • Exit → removed (--rm)

   - Container 3: docker run --rm <image> --prefix Prod_New_ --target-workspace Prod_New_
       • Auth + Copy + Rebind (prefix Prod_New_)
       • Exit → removed (--rm)

4) Final state
   - Dev workspace: Dev-prefixed items (Dev-*)
   - Test workspace: Test-prefixed items (Test-*)
   - Prod workspace: Prod_New_-prefixed items (Prod_New_*)
```


## 🚀 Features
- **Blue-Green Deployment Strategy** - Zero-downtime deployments with prefix-based naming
- **Multi-Environment Support** - Dev, Test, and Production deployments
- **Fabric CLI Integration** - Uses Microsoft Fabric CLI for workspace operations
- **Power BI REST API** - Handles report rebinding and ID resolution
- **Azure DevOps Integration** - Complete CI/CD pipeline automation
- **Service Principal Authentication** - Secure, automated authentication
- **Retry Logic** - Built-in retry mechanisms for API calls
- **Cross-Workspace Deployment** - Copy and deploy across different Fabric workspaces

## 📋 Prerequisites

### 1. Azure/Microsoft 365 Setup
- **Microsoft Fabric/Power BI Premium** workspace access
- **Azure App Registration** (Service Principal) with:
  - Client ID, Client Secret, Tenant ID
  - Power BI Service API permissions
  - Fabric workspace member access

### 2. Azure DevOps Setup
- **Azure DevOps Project** with repository access
- **Variable Groups** configured:
  - `Fabric-ServicePrincipal` (FabricClientId, FabricClientSecret, FabricTenantId)
  - `Fabric-DeploymentSettings` (workspace and item names)
- **Docker Hub Service Connection** named `dockerhub-connection`

### 3. Docker Hub
- Docker Hub account and repository: `nalakan/pbi_blue_green_dep_v1`

## ⚙️ Configuration

### Required Environment Variables
| Variable | Description | Example |
|----------|-------------|---------|
| `FABRIC_CLIENT_ID` | Azure App Registration Client ID | `12345678-1234-1234-1234-123456789012` |
| `FABRIC_CLIENT_SECRET` | Azure App Registration Client Secret | `your-secret-key` |
| `FABRIC_TENANT_ID` | Azure Tenant ID | `87654321-4321-4321-4321-210987654321` |

### Azure DevOps Variable Groups

#### Fabric-ServicePrincipal Variables
```yaml
FabricClientId: "your-client-id"
FabricClientSecret: "your-client-secret"  # Mark as secret
FabricTenantId: "your-tenant-id"
```

#### Fabric-DeploymentSettings Variables
```yaml
ProdWorkspaceName: "Production Workspace"
DevWorkspaceName: "Development Workspace"
TestWorkspaceName: "Test Workspace"
FabricReportName: "Your Report Name"
FabricModelName: "Your Semantic Model Name"
```

## 🐳 Usage

### Direct Docker Usage
```bash
# Pull the latest image
docker pull nalakan/pbi_blue_green_dep_v1:latest

# Run deployment
docker run --rm \
  -e FABRIC_CLIENT_ID="your-client-id" \
  -e FABRIC_CLIENT_SECRET="your-client-secret" \
  -e FABRIC_TENANT_ID="your-tenant-id" \
  nalakan/pbi_blue_green_dep_v1:latest \
    --source-workspace "Production Workspace" \
    --target-workspace "Development Workspace" \
    --report-name "Sales Report" \
    --semantic-model-name "Sales Model" \
    --prefix "Dev-"
```

### Command Line Arguments
| Argument | Required | Description | Example |
|----------|----------|-------------|---------|
| `--source-workspace` | Yes | Source Fabric workspace name | `"Production Workspace"` |
| `--target-workspace` | Yes | Target Fabric workspace name | `"Development Workspace"` |
| `--report-name` | Yes | Name of the report to copy | `"Sales Report"` |
| `--semantic-model-name` | Yes | Name of the semantic model to copy | `"Sales Model"` |
| `--prefix` | Yes | Prefix for new items | `"Dev-"`, `"Test-"`, `"Prod_New_"` |

## 🔄 CI/CD Pipeline Process

### Stage 1: Build Image (`azure-pipelines-build-image.yml`)
**Trigger:** Automatic on changes to main branch
1. **Repository Checkout** - Gets latest code
2. **Line Ending Normalization** - Fixes Windows/Linux compatibility
3. **Docker Build & Push** - Builds image and pushes to Docker Hub
4. **Tags Applied** - Both build ID and 'latest' tags

### Stage 2: Deploy (`azure-pipelines-deploy-image.yml`)
**Trigger:** Manual execution
1. **Image Pull** - Downloads latest image from Docker Hub
2. **Dev Deployment** - Copies items with "Dev-" prefix
3. **Test Deployment** - Copies items with "Test-" prefix
4. **Production Deployment** - Copies items with "Prod_New_" prefix

## 🔧 Container Internal Process

### Authentication Flow
```bash
# 1. Set Fabric CLI encryption fallback
fab config set encryption_fallback_enabled true

# 2. Authenticate using service principal
fab auth login -u "$FABRIC_CLIENT_ID" -p "$FABRIC_CLIENT_SECRET" --tenant "$FABRIC_TENANT_ID"

# 3. Verify authentication
fab --version
```

### Deployment Steps
1. **Copy Semantic Model** - Uses Fabric CLI `fab cp` command
2. **Copy Report** - Uses Fabric CLI `fab cp` command  
3. **Get Access Token** - OAuth2 client credentials flow
4. **Resolve Workspace ID** - Power BI REST API call
5. **Find Dataset ID** - Retry logic with Power BI API
6. **Find Report ID** - Retry logic with Power BI API
7. **Rebind Report** - Links report to new semantic model

## 🔍 Troubleshooting

### Common Issues

#### Authentication Failures
```bash
# Check service principal permissions
fab auth login -u "$FABRIC_CLIENT_ID" -p "$FABRIC_CLIENT_SECRET" --tenant "$FABRIC_TENANT_ID"
```
**Solutions:**
- Verify service principal has Fabric workspace member access
- Check Power BI Service API permissions in Azure
- Ensure admin consent granted for API permissions

#### Item Not Found Errors
**Solutions:**
- Verify exact workspace and item names (case-sensitive)
- Check that source items exist in source workspace
- Wait for items to appear after copy (retry logic handles this)

#### Network/Timeout Issues
**Solutions:**
- Container includes 60-second timeouts for API calls
- Built-in retry logic for Power BI API rate limits
- Check firewall/network restrictions

### Debug Mode
```bash
# Run with verbose output
docker run --rm \
  -e FABRIC_CLIENT_ID="your-client-id" \
  -e FABRIC_CLIENT_SECRET="your-client-secret" \
  -e FABRIC_TENANT_ID="your-tenant-id" \
  nalakan/pbi_blue_green_dep_v1:latest \
    --source-workspace "Prod" \
    --target-workspace "Dev" \
    --report-name "Report" \
    --semantic-model-name "Model" \
    --prefix "Dev-"
```

## 📊 Example Deployment Scenarios

### Scenario 1: Development Environment Refresh
```yaml
Pipeline Step: "Deploy to Dev" 
Container Command: docker run --rm ... --prefix Dev- --target-workspace "Development Workspace"
Process: Container 1 → Auth → Copy → Rebind → Destroy
Source: "Production Workspace/Sales Report" 
Target: "Development Workspace/Dev-Sales Report"
Result: Dev report rebound to Dev semantic model, container destroyed
```

### Scenario 2: Blue-Green Production Deployment  
```yaml
Pipeline Step: "Deploy to Prod_New"
Container Command: docker run --rm ... --prefix Prod_New_ --target-workspace "Production Workspace"
Process: Container 3 → Auth → Copy → Rebind → Destroy  
Source: "Production Workspace/Sales Report"
Target: "Production Workspace/Prod_New_Sales Report"
Result: New production version created alongside current, container destroyed
```

### Scenario 3: Testing Environment Update
```yaml
Pipeline Step: "Deploy to Test"
Container Command: docker run --rm ... --prefix Test- --target-workspace "Test Workspace"
Process: Container 2 → Auth → Copy → Rebind → Destroy
Source: "Production Workspace/Dashboard"
Target: "Test Workspace/Test-Dashboard" 
Result: Test environment updated with latest production version, container destroyed
```

### Complete Pipeline Execution Example
```bash
# Azure DevOps runs these three commands sequentially:

# Step 1: Dev deployment (Container 1)
docker run --rm nalakan/pbi_blue_green_dep_v1:latest \
  --source-workspace "Production" --target-workspace "Development" \
  --prefix Dev- --report-name "Sales Report" --semantic-model-name "Sales Model"
# Container 1 destroyed after completion

# Step 2: Test deployment (Container 2)  
docker run --rm nalakan/pbi_blue_green_dep_v1:latest \
  --source-workspace "Production" --target-workspace "Test" \
  --prefix Test- --report-name "Sales Report" --semantic-model-name "Sales Model"
# Container 2 destroyed after completion

# Step 3: Prod_New deployment (Container 3)
docker run --rm nalakan/pbi_blue_green_dep_v1:latest \
  --source-workspace "Production" --target-workspace "Production" \
  --prefix Prod_New_ --report-name "Sales Report" --semantic-model-name "Sales Model"  
# Container 3 destroyed after completion

# Result: Three independent deployments completed, no containers remain
```

## 🏷️ Container Tags
- **`latest`** - Most recent stable build
- **`{buildId}`** - Specific Azure DevOps build version

## 🔗 Related Resources
- [Microsoft Fabric CLI Documentation](https://docs.microsoft.com/fabric/cli)
- [Power BI REST API Reference](https://docs.microsoft.com/rest/api/power-bi/)
- [Azure DevOps Docker Tasks](https://docs.microsoft.com/azure/devops/pipelines/tasks/build/docker)

## 📝 Notes
- Service principal must be added as member to both source and target workspaces
- Items are copied with force flag (`-f`) to overwrite existing items
- Report rebinding happens automatically after successful copy
- Built-in retry logic handles eventual consistency delays
- Container exits with appropriate error codes for CI/CD integration

## 🐛 Support
For issues and questions:
1. Check Azure DevOps pipeline logs
2. Verify service principal permissions
3. Ensure workspace and item names are correct
4. Review Fabric workspace member access

---
**Repository:** [nalakan/pbi_blue_green_dep_v1](https://hub.docker.com/repository/docker/nalakan/pbi_blue_green_dep_v1/general)  
**Build Pipeline:** Azure DevOps CI/CD  
**Base Image:** Python with Fabric CLI
