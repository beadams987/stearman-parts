# Phase 3 Status — API Deployment Complete

**Date:** 2026-03-13  
**Status:** ✅ COMPLETE — API is live and returning data

---

## What Was Done

### 1. Azure Functions v2 Wrapper
Created `api/function_app.py` using the ASGI adapter:
```python
import azure.functions as func
from app.main import app as fastapi_app
app = func.AsgiFunctionApp(app=fastapi_app, http_auth_level=func.AuthLevel.ANONYMOUS)
```

### 2. host.json — Critical Fix
Created `api/host.json` with `routePrefix: ""` (empty) to avoid double-slash
routing error (`api//{*route}`) that prevented the Azure Functions host from starting.

### 3. Config Env Var Alignment
Updated `api/app/config.py` to use env vars matching those set on the Function App:
- `AZURE_STORAGE_CONNECTION_STRING` → `AZURE_BLOB_CONNECTION_STRING`
- `AZURE_STORAGE_CONTAINER` → `BLOB_CONTAINER_NAME` (default: "images")
- Added `BLOB_THUMBS_CONTAINER_NAME` (set to "thumbnails" on Function App)
- Changed CORS default to `*` (override via `CORS_ORIGINS` env var)

Updated `api/app/routers/images.py` to use new attribute names.

### 4. Azure Functions Requirements
Added `azure-functions>=1.21.0` to `api/requirements.txt`.

### 5. Azure Infrastructure Fixes
- **Enabled basic publishing credentials** (was disabled, causing 401 on Kudu auth)
- **Set SCM_DO_BUILD_DURING_DEPLOYMENT=true** and **ENABLE_ORYX_BUILD=true**
- Set `WEBSITE_RUN_FROM_PACKAGE=1` (required for Linux Consumption plan)

### 6. CI Workflow Updates
Updated `.github/workflows/ci.yml` deploy-api job to pre-install dependencies:
```yaml
- name: Install dependencies into package dir
  run: |
    pip install -r api/requirements.txt \
      --target api/.python_packages/lib/site-packages
```
With `scm-do-build-during-deployment: false` (deps are pre-packaged).

### 7. Frontend Config
The CI already had `VITE_API_URL: https://func-stearman-api.azurewebsites.net/api` set.
The frontend SPA deployed to stearmanparts.com is now wired to the live API.

---

## Live API Verification

```
GET https://func-stearman-api.azurewebsites.net/health
→ {"status":"ok"}

GET https://func-stearman-api.azurewebsites.net/api/folders
→ 4 folders (DISC_1..4_STEARMAN)

GET https://func-stearman-api.azurewebsites.net/api/search?q=cowl
→ total_count: 345, results: 50

GET https://func-stearman-api.azurewebsites.net/api/stats
→ {"total_images":7673,"total_folders":21,"total_bundles":396,"total_indexes":19826}
```

---

## Notes / Known Issues

1. **Health endpoint URL**: The health check is at `/health` (not `/api/health`) because
   `routePrefix=""` passes paths directly to FastAPI. The frontend uses `/api/...` routes
   which work correctly.

2. **CI deploy**: Future pushes to main will trigger the functions-action which now
   pre-packages dependencies. First CI run after this commit will confirm it works end-to-end.

3. **CORS**: Currently set to `*`. Can be locked down by setting `CORS_ORIGINS` env var
   on the Function App to `https://stearmanparts.com,https://www.stearmanparts.com`.

4. **Auth (WorkOS)**: WorkOS env vars are empty — auth is optional per the code
   (`optional_auth` dependency). Search and browse work without auth.

---

## Commits
- `623c962` — feat: add Azure Functions v2 wrapper and fix env var names
- `58f78fc` — fix: host.json routePrefix and CI dependency packaging
# Phase 3 deployment
