"""Folder browsing endpoints."""

from __future__ import annotations

from typing import Annotated

import pyodbc
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import CurrentUser, optional_auth
from app.database import get_db
import math

from app.config import Settings, get_settings
from app.models import FolderResponse, ImageResponse, PaginatedResponse
from app.services.blob_service import BlobService

router = APIRouter(prefix="/api/folders", tags=["folders"])


def _row_to_folder(row: pyodbc.Row) -> FolderResponse:
    return FolderResponse(
        id=row.FolderID,
        name=row.FolderName,
        folder_name=row.FolderName,
        parent_id=row.ParentFolderID if row.ParentFolderID else None,
        children_count=getattr(row, "ChildrenCount", 0),
        image_count=getattr(row, "ImageCount", 0),
    )


@router.get("", response_model=list[FolderResponse])
async def list_folders(
    conn: Annotated[pyodbc.Connection, Depends(get_db)],
    _user: Annotated[CurrentUser | None, Depends(optional_auth)],
    parent_id: int | None = Query(default=None, description="Parent folder ID; omit for root folders"),
) -> list[FolderResponse]:
    """List folders.

    When ``parent_id`` is omitted the root-level folders are returned.
    Pass a ``parent_id`` to fetch the children of that folder.
    """
    cursor = conn.cursor()

    if parent_id is None:
        cursor.execute(
            """
            SELECT f.FolderID, f.FolderName, f.ParentFolderID,
                   (SELECT COUNT(*) FROM Folders c WHERE c.ParentFolderID = f.FolderID) AS ChildrenCount,
                   (SELECT COUNT(*) FROM Images i WHERE i.FolderID = f.FolderID) AS ImageCount
            FROM Folders f
            WHERE f.ParentFolderID IS NULL
            ORDER BY f.SortOrder, f.FolderName
            """
        )
    else:
        cursor.execute(
            """
            SELECT f.FolderID, f.FolderName, f.ParentFolderID,
                   (SELECT COUNT(*) FROM Folders c WHERE c.ParentFolderID = f.FolderID) AS ChildrenCount,
                   (SELECT COUNT(*) FROM Images i WHERE i.FolderID = f.FolderID) AS ImageCount
            FROM Folders f
            WHERE f.ParentFolderID = ?
            ORDER BY f.SortOrder, f.FolderName
            """,
            parent_id,
        )

    return [_row_to_folder(row) for row in cursor.fetchall()]


@router.get("/{folder_id}", response_model=FolderResponse)
async def get_folder(
    folder_id: int,
    conn: Annotated[pyodbc.Connection, Depends(get_db)],
    _user: Annotated[CurrentUser | None, Depends(optional_auth)],
) -> FolderResponse:
    """Return a single folder with child and image counts."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT f.FolderID, f.FolderName, f.ParentFolderID,
               (SELECT COUNT(*) FROM Folders c WHERE c.ParentFolderID = f.FolderID) AS ChildrenCount,
               (SELECT COUNT(*) FROM Images i WHERE i.FolderID = f.FolderID) AS ImageCount
        FROM Folders f
        WHERE f.FolderID = ?
        """,
        folder_id,
    )
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found.")
    return _row_to_folder(row)


@router.get("/{folder_id}/images")
async def list_folder_images(
    folder_id: int,
    conn: Annotated[pyodbc.Connection, Depends(get_db)],
    _user: Annotated[CurrentUser | None, Depends(optional_auth)],
    settings: Annotated[Settings, Depends(get_settings)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> PaginatedResponse[ImageResponse]:
    """Return paginated images belonging to a folder."""
    cursor = conn.cursor()
    thumbs_svc = BlobService(settings.AZURE_BLOB_CONNECTION_STRING, settings.BLOB_THUMBS_CONTAINER_NAME) if settings.AZURE_BLOB_CONNECTION_STRING else None

    # Verify folder exists and get total count
    cursor.execute("SELECT COUNT(*) FROM Images WHERE FolderID = ?", folder_id)
    count_row = cursor.fetchone()
    if count_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found.")
    total = count_row[0]

    offset = (page - 1) * page_size
    cursor.execute(
        """
        SELECT i.ImageID, i.FolderID, i.BundleID, i.BundleOffset,
               i.ImagePosition, i.OriginalFileName, i.ThumbnailPath,
               i.ImageWidth, i.ImageHeight
        FROM Images i
        WHERE i.FolderID = ?
        ORDER BY i.ImagePosition, i.BundleOffset
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """,
        folder_id,
        offset,
        page_size,
    )
    images = cursor.fetchall()

    results: list[ImageResponse] = []
    for img in images:
        image_id = img.ImageID

        # Fetch drawing numbers
        cursor.execute(
            """
            SELECT ix.IndexValue FROM ImageIndexes ix
            JOIN IndexTypes it ON ix.IndexTypeID = it.IndexTypeID
            WHERE ix.ImageID = ? AND it.Code = 'DG'
            """,
            image_id,
        )
        drawing_numbers = [r.IndexValue for r in cursor.fetchall()]

        # Fetch keywords
        cursor.execute(
            """
            SELECT ix.IndexValue FROM ImageIndexes ix
            JOIN IndexTypes it ON ix.IndexTypeID = it.IndexTypeID
            WHERE ix.ImageID = ? AND it.Code = 'KW'
            """,
            image_id,
        )
        keywords = [r.IndexValue for r in cursor.fetchall()]

        results.append(
            ImageResponse(
                id=image_id,
                folder_id=img.FolderID,
                bundle_id=img.BundleID,
                bundle_offset=img.BundleOffset,
                image_position=img.ImagePosition,
                file_name=img.OriginalFileName,
                thumbnail_url=thumbs_svc.get_thumbnail_url(img.ThumbnailPath) if img.ThumbnailPath and thumbs_svc else img.ThumbnailPath,
                width=img.ImageWidth,
                height=img.ImageHeight,
                drawing_numbers=drawing_numbers,
                keywords=keywords,
            )
        )

    return PaginatedResponse[ImageResponse](
        items=results,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )
