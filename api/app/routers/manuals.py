"""Manual PDF download endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.services.blob_service import BlobService

router = APIRouter(prefix="/api/manuals", tags=["manuals"])


class ManualInfo(BaseModel):
    id: str
    title: str
    description: str
    filename: str
    size_mb: int


# Hardcoded manual catalog — expand as new PDFs are added
MANUALS: list[ManualInfo] = [
    ManualInfo(
        id="erection-maintenance",
        title="Erection & Maintenance Instructions",
        description="Army Model PT-13D and Navy Model N2S-5",
        filename="Stearman_Erection_and_Maintenance_Instructions_PT-13D_N2S-5.pdf",
        size_mb=23,
    ),
    ManualInfo(
        id="parts-catalog",
        title="Parts Catalog",
        description="Army Model PT-13D and Navy Model N2S-5",
        filename="Stearman_Parts_Catalog_PT-13D_N2S-5.pdf",
        size_mb=149,
    ),
]

_MANUALS_BY_ID = {m.id: m for m in MANUALS}


def _get_manuals_blob_service(settings: Settings) -> BlobService:
    return BlobService(
        settings.AZURE_BLOB_CONNECTION_STRING,
        settings.BLOB_MANUALS_CONTAINER_NAME,
    )


@router.get("", response_model=list[ManualInfo])
async def list_manuals() -> list[ManualInfo]:
    """Return the list of available PDF manuals."""
    return MANUALS


@router.get("/{manual_id}/download")
async def download_manual(
    manual_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RedirectResponse:
    """Generate a time-limited SAS URL for the manual PDF and redirect."""
    manual = _MANUALS_BY_ID.get(manual_id)
    if not manual:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Manual '{manual_id}' not found",
        )

    blob_service = _get_manuals_blob_service(settings)
    url = blob_service.get_blob_url(manual.filename)
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)
