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
from app.models import ImageDetailResponse, ImageResponse, FolderBreadcrumb
from app.services.blob_service import BlobService

router = APIRouter(prefix="/api/images", tags=["images"])


class NotesUpdate(BaseModel):
    notes: str


def _get_blob_service(settings: Settings) -> BlobService:
    return BlobService(settings.AZURE_BLOB_CONNECTION_STRING, settings.BLOB_CONTAINER_NAME)


def _get_thumbs_blob_service(settings: Settings) -> BlobService:
    """Return a BlobService pointed at the thumbnails container."""
    return BlobService(settings.AZURE_BLOB_CONNECTION_STRING, settings.BLOB_THUMBS_CONTAINER_NAME)


def _get_renders_blob_service(settings: Settings) -> BlobService:
    """Return a BlobService pointed at the pre-rendered JPEGs container."""
    return BlobService(settings.AZURE_BLOB_CONNECTION_STRING, settings.BLOB_RENDERS_CONTAINER_NAME)


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
               i.Notes, i.SourceDiscNumber, i.SourceImageID, i.CreatedAt,
               i.RenderPath
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

    # Generate thumbnail URL if path exists (thumbnails are in a separate container)
    thumbnail_url: str | None = None
    thumbs_svc = _get_thumbs_blob_service(settings) if settings.AZURE_BLOB_CONNECTION_STRING else None
    if row.ThumbnailPath and thumbs_svc:
        thumbnail_url = thumbs_svc.get_thumbnail_url(row.ThumbnailPath)

    # Generate full blob URL if path exists
    blob_url: str | None = None
    if row.BlobPath and settings.AZURE_BLOB_CONNECTION_STRING:
        blob_svc = _get_blob_service(settings)
        blob_url = blob_svc.get_image_url(row.BlobPath)

    # Generate render URL: prefer pre-rendered JPEG from renders container,
    # fall back to the on-the-fly /render endpoint
    render_url: str | None = None
    render_path = getattr(row, "RenderPath", None)
    if render_path and settings.AZURE_BLOB_CONNECTION_STRING:
        renders_svc = _get_renders_blob_service(settings)
        render_url = renders_svc.get_render_url(render_path)

    # Build folder breadcrumb path
    folder_path: list[FolderBreadcrumb] = []
    current_folder_id = row.FolderID
    while current_folder_id is not None:
        cursor.execute(
            "SELECT FolderID, FolderName, ParentFolderID FROM Folders WHERE FolderID = ?",
            current_folder_id,
        )
        f = cursor.fetchone()
        if f is None:
            break
        folder_path.insert(0, FolderBreadcrumb(id=f.FolderID, folder_name=f.FolderName))
        current_folder_id = f.ParentFolderID

    # Get folder name
    folder_name = folder_path[-1].folder_name if folder_path else None

    # Get related images from same folder (up to 12, excluding this image)
    cursor.execute(
        """
        SELECT TOP 12 i.ImageID, i.FolderID, i.BundleID, i.BundleOffset,
               i.ImagePosition, i.OriginalFileName, i.ThumbnailPath
        FROM Images i
        WHERE i.FolderID = ? AND i.ImageID != ?
        ORDER BY ABS(i.ImagePosition - ?)
        """,
        row.FolderID,
        image_id,
        row.ImagePosition,
    )
    related_images: list[ImageResponse] = []
    for rel in cursor.fetchall():
        rel_thumb = None
        if rel.ThumbnailPath and thumbs_svc:
            rel_thumb = thumbs_svc.get_thumbnail_url(rel.ThumbnailPath)
        related_images.append(ImageResponse(
            id=rel.ImageID,
            folder_id=rel.FolderID,
            file_name=rel.OriginalFileName,
            image_position=rel.ImagePosition,
            bundle_id=rel.BundleID,
            bundle_offset=rel.BundleOffset,
            thumbnail_url=rel_thumb,
        ))

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
        file_name=row.OriginalFileName,
        image_position=row.ImagePosition,
        thumbnail_url=thumbnail_url,
        drawing_numbers=drawing_numbers,
        keywords=keywords,
        image_url=blob_url,
        render_url=render_url,
        dzi_url=None,  # DZI not yet implemented
        notes=row.Notes,
        folder_name=folder_name,
        folder_path=folder_path,
        related_images=related_images,
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
