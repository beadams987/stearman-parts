"""Image detail, viewing, download, and annotation endpoints."""

from __future__ import annotations

from typing import Annotated

import pyodbc
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel

from app.auth import CurrentUser, optional_auth, verify_token
from app.config import Settings, get_settings
from app.database import get_db
from app.models import ImageDetailResponse
from app.services.blob_service import BlobService

router = APIRouter(prefix="/api/images", tags=["images"])


class NotesUpdate(BaseModel):
    notes: str


def _get_blob_service(settings: Settings) -> BlobService:
    return BlobService(settings.AZURE_STORAGE_CONNECTION_STRING, settings.AZURE_STORAGE_CONTAINER)


def _log_audit(
    conn: pyodbc.Connection,
    *,
    user_id: str | None,
    action: str,
    entity_type: str,
    entity_id: int,
    details: str | None = None,
) -> None:
    """Insert a row into the AuditLog table."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO AuditLog (UserID, Action, EntityType, EntityID, Details)
        VALUES (?, ?, ?, ?, ?)
        """,
        user_id,
        action,
        entity_type,
        entity_id,
        details,
    )
    conn.commit()


@router.get("/{image_id}", response_model=ImageDetailResponse)
async def get_image(
    image_id: int,
    conn: Annotated[pyodbc.Connection, Depends(get_db)],
    user: Annotated[CurrentUser | None, Depends(optional_auth)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImageDetailResponse:
    """Return full image metadata including indexes."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT i.ImageID, i.FolderID, i.BundleID, i.BundleOffset,
               i.ImagePosition, i.OriginalFileName, i.ThumbnailPath,
               i.BlobPath, i.ImageWidth, i.ImageHeight,
               i.Notes, i.SourceDiscNumber, i.SourceImageID, i.CreatedAt
        FROM Images i
        WHERE i.ImageID = ?
        """,
        image_id,
    )
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")

    # Drawing numbers
    cursor.execute(
        """
        SELECT ix.IndexValue FROM ImageIndexes ix
        JOIN IndexTypes it ON ix.IndexTypeID = it.IndexTypeID
        WHERE ix.ImageID = ? AND it.Code = 'DG'
        """,
        image_id,
    )
    drawing_numbers = [r.IndexValue for r in cursor.fetchall()]

    # Keywords
    cursor.execute(
        """
        SELECT ix.IndexValue FROM ImageIndexes ix
        JOIN IndexTypes it ON ix.IndexTypeID = it.IndexTypeID
        WHERE ix.ImageID = ? AND it.Code = 'KW'
        """,
        image_id,
    )
    keywords = [r.IndexValue for r in cursor.fetchall()]

    # Generate thumbnail URL if path exists
    thumbnail_url: str | None = None
    if row.ThumbnailPath and settings.AZURE_STORAGE_CONNECTION_STRING:
        blob_svc = _get_blob_service(settings)
        thumbnail_url = blob_svc.get_thumbnail_url(row.ThumbnailPath)

    # Generate full blob URL if path exists
    blob_url: str | None = None
    if row.BlobPath and settings.AZURE_STORAGE_CONNECTION_STRING:
        blob_svc = _get_blob_service(settings)
        blob_url = blob_svc.get_image_url(row.BlobPath)

    # Audit the view
    _log_audit(
        conn,
        user_id=user["id"] if user else None,
        action="VIEW",
        entity_type="Image",
        entity_id=image_id,
    )

    return ImageDetailResponse(
        id=row.ImageID,
        folder_id=row.FolderID,
        bundle_id=row.BundleID,
        bundle_offset=row.BundleOffset,
        position=row.ImagePosition,
        filename=row.OriginalFileName,
        thumbnail_url=thumbnail_url,
        width=row.ImageWidth,
        height=row.ImageHeight,
        drawing_numbers=drawing_numbers,
        keywords=keywords,
        blob_url=blob_url,
        notes=row.Notes,
        source_disc=row.SourceDiscNumber,
        source_image_id=row.SourceImageID,
        created_at=row.CreatedAt,
    )


@router.get("/{image_id}/view")
async def view_image(
    image_id: int,
    conn: Annotated[pyodbc.Connection, Depends(get_db)],
    user: Annotated[CurrentUser | None, Depends(optional_auth)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RedirectResponse:
    """Redirect to a time-limited SAS URL for the full-resolution image."""
    cursor = conn.cursor()
    cursor.execute("SELECT BlobPath FROM Images WHERE ImageID = ?", image_id)
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")
    if not row.BlobPath:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image blob not available.")

    blob_svc = _get_blob_service(settings)
    sas_url = blob_svc.get_image_url(row.BlobPath)

    _log_audit(
        conn,
        user_id=user["id"] if user else None,
        action="VIEW",
        entity_type="Image",
        entity_id=image_id,
        details="full-resolution redirect",
    )

    return RedirectResponse(url=sas_url, status_code=status.HTTP_302_FOUND)


@router.get("/{image_id}/download")
async def download_image(
    image_id: int,
    conn: Annotated[pyodbc.Connection, Depends(get_db)],
    user: Annotated[CurrentUser | None, Depends(optional_auth)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    """Download the original TIFF with a Content-Disposition header."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT BlobPath, OriginalFileName, MimeType FROM Images WHERE ImageID = ?",
        image_id,
    )
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")
    if not row.BlobPath:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image blob not available.")

    blob_svc = _get_blob_service(settings)
    container_client = blob_svc._container_client
    blob_client = container_client.get_blob_client(row.BlobPath)
    download_stream = blob_client.download_blob()

    filename = row.OriginalFileName or f"image_{image_id}.tif"
    content_type = row.MimeType or "image/tiff"

    _log_audit(
        conn,
        user_id=user["id"] if user else None,
        action="EXPORT",
        entity_type="Image",
        entity_id=image_id,
        details="download original",
    )

    return StreamingResponse(
        download_stream.chunks(),
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{image_id}/notes", status_code=status.HTTP_200_OK)
async def update_notes(
    image_id: int,
    body: NotesUpdate,
    conn: Annotated[pyodbc.Connection, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(verify_token)],
) -> dict[str, str]:
    """Update the notes field on an image. Requires authentication."""
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM Images WHERE ImageID = ?", image_id)
    if cursor.fetchone() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")

    cursor.execute(
        "UPDATE Images SET Notes = ?, ModifiedAt = GETUTCDATE() WHERE ImageID = ?",
        body.notes,
        image_id,
    )
    conn.commit()

    _log_audit(
        conn,
        user_id=user["id"],
        action="NOTE_EDIT",
        entity_type="Image",
        entity_id=image_id,
        details=f"Updated notes ({len(body.notes)} chars)",
    )

    return {"status": "ok"}
