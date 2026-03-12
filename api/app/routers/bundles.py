"""Bundle (multi-page document group) endpoints."""

from __future__ import annotations

from typing import Annotated

import pyodbc
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, optional_auth
from app.database import get_db
from app.models import BundleResponse, ImageResponse

router = APIRouter(prefix="/api/bundles", tags=["bundles"])


@router.get("/{bundle_id}", response_model=BundleResponse)
async def get_bundle(
    bundle_id: int,
    conn: Annotated[pyodbc.Connection, Depends(get_db)],
    _user: Annotated[CurrentUser | None, Depends(optional_auth)],
) -> BundleResponse:
    """Return a bundle with all of its pages and their indexes."""
    cursor = conn.cursor()

    # Fetch the bundle itself
    cursor.execute(
        """
        SELECT b.BundleID, b.FolderID, b.ImagePosition
        FROM Bundles b
        WHERE b.BundleID = ?
        """,
        bundle_id,
    )
    bundle_row = cursor.fetchone()
    if bundle_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found.")

    # Fetch pages (images) belonging to this bundle
    cursor.execute(
        """
        SELECT i.ImageID, i.FolderID, i.BundleID, i.BundleOffset,
               i.ImagePosition, i.OriginalFileName, i.ThumbnailPath,
               i.ImageWidth, i.ImageHeight
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

        pages.append(
            ImageResponse(
                id=image_id,
                folder_id=img.FolderID,
                bundle_id=img.BundleID,
                bundle_offset=img.BundleOffset,
                position=img.ImagePosition,
                filename=img.OriginalFileName,
                thumbnail_url=img.ThumbnailPath,
                width=img.ImageWidth,
                height=img.ImageHeight,
                drawing_numbers=drawing_numbers,
                keywords=keywords,
            )
        )

    return BundleResponse(
        id=bundle_row.BundleID,
        folder_id=bundle_row.FolderID,
        position=bundle_row.ImagePosition,
        page_count=len(pages),
        pages=pages,
    )
