"""Internal deploy endpoint — updates WEBSITE_RUN_FROM_PACKAGE via ARM using managed identity."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from app.config import Settings, get_settings
from fastapi import Depends
from typing import Annotated

router = APIRouter(prefix="/api/_deploy", tags=["deploy"])


class DeployRequest(BaseModel):
    blob_url: str
    commit: str | None = None


@router.post("/update-package")
async def update_package(
    req: DeployRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    x_deploy_key: str = Header(...),
) -> dict:
    """Update WEBSITE_RUN_FROM_PACKAGE via Azure ARM REST API using managed identity.

    Called by CI after uploading a new package blob.
    """
    # Verify deploy key
    if x_deploy_key != settings.DEPLOY_KEY:
        raise HTTPException(status_code=403, detail="Invalid deploy key")

    # Get managed identity token for ARM
    # Azure Functions uses IDENTITY_ENDPOINT + IDENTITY_HEADER (not IMDS)
    import os
    identity_endpoint = os.environ.get("IDENTITY_ENDPOINT")
    identity_header = os.environ.get("IDENTITY_HEADER")

    if not identity_endpoint or not identity_header:
        raise HTTPException(status_code=503, detail="Managed identity not available (IDENTITY_ENDPOINT not set)")

    async with httpx.AsyncClient() as client:
        token_resp = await client.get(
            identity_endpoint,
            params={
                "api-version": "2019-08-01",
                "resource": "https://management.azure.com/",
            },
            headers={"X-IDENTITY-HEADER": identity_header},
            timeout=10,
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Failed to get managed identity token: {token_resp.status_code}")
        token = token_resp.json()["access_token"]

    # Update app settings via ARM REST API
    sub_id = settings.AZURE_SUBSCRIPTION_ID
    rg = settings.AZURE_RESOURCE_GROUP
    app_name = settings.AZURE_FUNCTION_APP_NAME

    arm_url = (
        f"https://management.azure.com/subscriptions/{sub_id}"
        f"/resourceGroups/{rg}/providers/Microsoft.Web/sites/{app_name}"
        f"/config/appsettings/list?api-version=2023-12-01"
    )

    async with httpx.AsyncClient() as client:
        # First, list current settings
        list_resp = await client.post(
            arm_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if list_resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Failed to list settings: {list_resp.text}")

        current_settings = list_resp.json().get("properties", {})
        current_settings["WEBSITE_RUN_FROM_PACKAGE"] = req.blob_url
        if req.commit:
            current_settings["DEPLOY_COMMIT"] = req.commit

        # PUT updated settings
        put_url = (
            f"https://management.azure.com/subscriptions/{sub_id}"
            f"/resourceGroups/{rg}/providers/Microsoft.Web/sites/{app_name}"
            f"/config/appsettings?api-version=2023-12-01"
        )
        put_resp = await client.put(
            put_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"properties": current_settings},
            timeout=15,
        )
        if put_resp.status_code not in (200, 201):
            raise HTTPException(status_code=502, detail=f"Failed to update settings: {put_resp.text}")

    return {"status": "ok", "message": "WEBSITE_RUN_FROM_PACKAGE updated, app will restart"}
