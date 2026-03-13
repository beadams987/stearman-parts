"""Bundle (multi-page document group) endpoints."""

from __future__ import annotations

from typing import Annotated

import pyodbc
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, optional_auth
from app.config import Settings, get_settings
from app.database import get_db
from app.models import BundleResponse, ImageResponse
from app.services.blob_service import BlobService

router = APIRouter(prefix="/api/bundles", tags=["bundles"])


def _get_thumbs_blob_service(settings: Settings) -> BlobService:
    return BlobService(settings.AZURE_BLOB_CONNECTION_STRING, settings.BLOB_THUMBS_CONTAINER_NAME)


def _get_renders_blob_service(settings: Settings) -> BlobService:
    return BlobService(settings.AZURE_BLOB_CONNECTION_STRING, settings.BLOB_RENDERS_CONTAINER_NAME)


@router.get("/{bundle_id}", response_model=BundleResponse)
async def get_bundle(
    bundle_id: int,
    conn: Annotated[pyodbc.Connection, Depends(get_db)],
    _user: Annotated[CurrentUser | None, Depends(optional_auth)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BundleResponse:
    """Return a bundle with all of its pages and their indexes."""
    cursor = conn.cursor()

    # Fetch the bundle with folder info
    cursor.execute(
        """
        SELECT b.BundleID, b.FolderID, b.ImagePosition, f.FolderName
        FROM Bundles b
        LEFT JOIN Folders f ON b.FolderID = f.FolderID
        WHERE b.BundleID = ?
        """,
        bundle_id,
    )
    bundle_row = cursor.fetchone()
    if bundle_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found.")

    # Get bundle-level drawing numbers and keywords (from first page or all pages)
    cursor.execute(
        """
        SELECT DISTINCT ix.IndexValue, it.Code
        FROM Images i
        JOIN ImageIndexes ix ON i.ImageID = ix.ImageID
        JOIN IndexTypes it ON ix.IndexTypeID = it.IndexTypeID
        WHERE i.BundleID = ? AND it.Code IN ('DG', 'KW')
        """,
        bundle_id,
    )
    bundle_drawing_numbers: list[str] = []
    bundle_keywords: list[str] = []
    for row in cursor.fetchall():
        if row.Code == "DG":
            bundle_drawing_numbers.append(row.IndexValue)
        elif row.Code == "KW":
            bundle_keywords.append(row.IndexValue)

    # Build blob services for SAS URL generation
    thumbs_svc = _get_thumbs_blob_service(settings) if settings.AZURE_BLOB_CONNECTION_STRING else None
    renders_svc = _get_renders_blob_service(settings) if settings.AZURE_BLOB_CONNECTION_STRING else None

    # Fetch pages (images) belonging to this bundle
    cursor.execute(
        """
        SELECT i.ImageID, i.FolderID, i.BundleID, i.BundleOffset,
               i.ImagePosition, i.OriginalFileName, i.ThumbnailPath,
               i.RenderPath, i.ImageWidth, i.ImageHeight
        FROM Images i
        WHERE i.BundleID = ?
        ORDER BY i.BundleOffset
        """,
        bundle_id,
    )
    image_rows = cursor.fetchall()

    pages: list[ImageResponse] = []
    for img in image_rows:
        image_id = img.ImageID

        # Drawing numbers for this image
        cursor.execute(
            """
            SELECT ix.IndexValue FROM ImageIndexes ix
            JOIN IndexTypes it ON ix.IndexTypeID = it.IndexTypeID
            WHERE ix.ImageID = ? AND it.Code = 'DG'
            """,
            image_id,
        )
        drawing_numbers = [r.IndexValue for r in cursor.fetchall()]

        # Keywords for this image
        cursor.execute(
            """
            SELECT ix.IndexValue FROM ImageIndexes ix
            JOIN IndexTypes it ON ix.IndexTypeID = it.IndexTypeID
            WHERE ix.ImageID = ? AND it.Code = 'KW'
            """,
            image_id,
        )
        keywords = [r.IndexValue for r in cursor.fetchall()]

        # Generate SAS URLs for thumbnails and renders
        thumbnail_url: str | None = None
        if img.ThumbnailPath and thumbs_svc:
            thumbnail_url = thumbs_svc.get_thumbnail_url(img.ThumbnailPath)

        render_url: str | None = None
        render_path = getattr(img, "RenderPath", None)
        if render_path and renders_svc:
            render_url = renders_svc.get_render_url(render_path)

        pages.append(
            ImageResponse(
                id=image_id,
                folder_id=img.FolderID,
                bundle_id=img.BundleID,
                bundle_offset=img.BundleOffset,
                file_name=img.OriginalFileName,
                thumbnail_url=thumbnail_url,
                render_url=render_url,
                drawing_numbers=drawing_numbers,
                keywords=keywords,
            )
        )

    return BundleResponse(
        id=bundle_row.BundleID,
        folder_id=bundle_row.FolderID,
        folder_name=bundle_row.FolderName,
        position=bundle_row.ImagePosition,
        image_position=bundle_row.ImagePosition,
        drawing_numbers=bundle_drawing_numbers,
        keywords=bundle_keywords,
        page_count=len(pages),
        pages=pages,
    )
