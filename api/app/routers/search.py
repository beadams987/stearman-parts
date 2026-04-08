"""Search endpoints with Azure AI Search and SQL LIKE fallback."""

from __future__ import annotations

import logging
import math
from typing import Annotated, Any

import pyodbc
from fastapi import APIRouter, Depends, Query

from app.auth import CurrentUser, optional_auth
from app.config import Settings, get_settings
from app.database import get_db
from app.models import SearchResponse, SearchResult
from app.services.blob_service import BlobService
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


def _get_thumbs_blob_service(settings: Settings) -> BlobService | None:
    """Return a BlobService for the thumbnails container, or None if not configured."""
    if not settings.AZURE_BLOB_CONNECTION_STRING:
        return None
    return BlobService(settings.AZURE_BLOB_CONNECTION_STRING, settings.BLOB_THUMBS_CONTAINER_NAME)


def _get_search_service(settings: Settings) -> SearchService | None:
    """Return a SearchService if Azure AI Search is configured, else None."""
    if settings.AZURE_SEARCH_ENDPOINT and settings.AZURE_SEARCH_KEY:
        return SearchService(
            endpoint=settings.AZURE_SEARCH_ENDPOINT,
            key=settings.AZURE_SEARCH_KEY,
            index_name=settings.AZURE_SEARCH_INDEX,
        )
    return None


def _sql_fallback_search(
    conn: pyodbc.Connection,
    query: str,
    *,
    index_type: str | None = None,
    folder_id: int | None = None,
    top: int = 50,
    skip: int = 0,
    thumbs_svc: BlobService | None = None,
) -> dict[str, Any]:
    """Fall back to SQL LIKE when Azure AI Search is not configured."""
    cursor = conn.cursor()

    conditions = ["ix.IndexValue LIKE ?"]
    params: list[Any] = [f"%{query}%"]

    if index_type == "drawing_number":
        conditions.append("it.Code = 'DG'")
    elif index_type == "keyword":
        conditions.append("it.Code = 'KW'")

    if folder_id is not None:
        conditions.append("i.FolderID = ?")
        params.append(folder_id)

    where = " AND ".join(conditions)

    # Also search OCR text and manual pages
    ocr_conditions = ["i.OcrText LIKE ?"]
    ocr_params: list[Any] = [f"%{query}%"]
    if folder_id is not None:
        ocr_conditions.append("i.FolderID = ?")
        ocr_params.append(folder_id)
    ocr_where = " AND ".join(ocr_conditions)

    # Count total matches (index matches + OCR matches)
    count_sql = f"""
        SELECT COUNT(*) FROM (
            SELECT DISTINCT i.ImageID
            FROM ImageIndexes ix
            JOIN IndexTypes it ON ix.IndexTypeID = it.IndexTypeID
            JOIN Images i ON ix.ImageID = i.ImageID
            WHERE {where}
            UNION
            SELECT DISTINCT i.ImageID
            FROM Images i
            WHERE {ocr_where}
        ) combined
    """
    all_count_params = params + ocr_params
    cursor.execute(count_sql, *all_count_params)
    total_count: int = cursor.fetchone()[0]

    # Fetch page of results — group by image, aggregate index values
    search_sql = f"""
        SELECT i.ImageID, i.OriginalFileName, i.ThumbnailPath, i.FolderID,
               ix.IndexValue, it.Name AS IndexTypeName,
               f.FolderName, i.BundleID
        FROM ImageIndexes ix
        JOIN IndexTypes it ON ix.IndexTypeID = it.IndexTypeID
        JOIN Images i ON ix.ImageID = i.ImageID
        JOIN Folders f ON i.FolderID = f.FolderID
        WHERE {where}
        ORDER BY ix.IndexValue
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """
    cursor.execute(search_sql, *params, skip, top)

    results: list[dict[str, Any]] = []
    for row in cursor.fetchall():
        index_type_name = row.IndexTypeName
        matched_field = "drawing_number" if index_type_name == "Drawing #" else "keyword"

        # Collect drawing numbers and keywords for this image
        drawing_numbers: list[str] = []
        keywords: list[str] = []
        if index_type_name == "Drawing #":
            drawing_numbers.append(row.IndexValue)
        else:
            keywords.append(row.IndexValue)

        # Generate SAS-signed thumbnail URL if possible; fall back to raw path
        thumb_url: str | None = None
        if row.ThumbnailPath:
            if thumbs_svc is not None:
                try:
                    thumb_url = thumbs_svc.get_thumbnail_url(row.ThumbnailPath)
                except Exception:
                    thumb_url = row.ThumbnailPath
            else:
                thumb_url = row.ThumbnailPath

        results.append({
            "id": row.ImageID,
            "type": "image",
            "file_name": row.OriginalFileName,
            "thumbnail_url": thumb_url,
            "folder_name": row.FolderName,
            "folder_id": row.FolderID,
            "matched_field": matched_field,
            "matched_value": row.IndexValue,
            "drawing_numbers": drawing_numbers,
            "keywords": keywords,
            "bundle_id": row.BundleID,
            "page_count": None,
        })

    return {"results": results, "total_count": total_count}


@router.get("", response_model=SearchResponse)
async def search(
    conn: Annotated[pyodbc.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[CurrentUser | None, Depends(optional_auth)],
    q: str = Query(..., min_length=1, description="Search query"),
    type: str | None = Query(default=None, description="Filter: 'drawing_number' or 'keyword'"),
    folder_id: int | None = Query(default=None, description="Limit to a specific folder"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> SearchResponse:
    """Full-text search across drawing numbers, keywords, and image metadata."""
    skip = (page - 1) * page_size

    search_svc = _get_search_service(settings)
    thumbs_svc = _get_thumbs_blob_service(settings)

    if search_svc is not None:
        try:
            data = search_svc.search(
                q,
                index_type=type,
                folder_id=folder_id,
                top=page_size,
                skip=skip,
            )
            # Sign thumbnail URLs for AI Search results
            if thumbs_svc is not None:
                for r in data.get("results", []):
                    raw = r.get("thumbnail_url")
                    if raw:
                        try:
                            r["thumbnail_url"] = thumbs_svc.get_thumbnail_url(raw)
                        except Exception:
                            pass  # keep raw path if signing fails
        except Exception:
            logger.exception("Azure AI Search failed; falling back to SQL LIKE")
            data = _sql_fallback_search(
                conn, q, index_type=type, folder_id=folder_id,
                top=page_size, skip=skip, thumbs_svc=thumbs_svc,
            )
    else:
        data = _sql_fallback_search(
            conn, q, index_type=type, folder_id=folder_id,
            top=page_size, skip=skip, thumbs_svc=thumbs_svc,
        )

    total = data.get("total_count", 0)
    total_pages = max(1, math.ceil(total / page_size))

    results = [SearchResult(**r) for r in data["results"]]
    return SearchResponse(
        results=results,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        query=q,
    )


@router.get("/suggest", response_model=list[SearchResult])
async def suggest(
    conn: Annotated[pyodbc.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[CurrentUser | None, Depends(optional_auth)],
    q: str = Query(..., min_length=1, description="Partial query for autocomplete"),
) -> list[SearchResult]:
    """Return up to 10 autocomplete suggestions for a partial query."""
    search_svc = _get_search_service(settings)

    if search_svc is not None:
        try:
            suggestions = search_svc.suggest(q, top=10)
            return [
                SearchResult(
                    id=s.get("id", ""),
                    type="image",
                    file_name=s.get("text", ""),
                    matched_field="keyword",
                    matched_value=s.get("text", ""),
                )
                for s in suggestions
            ]
        except Exception:
            logger.exception("Azure AI Search suggest failed; falling back to SQL")

    # SQL fallback: prefix match on IndexValue
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT TOP 10 ix.ImageID, ix.IndexValue, it.Name AS IndexTypeName, f.FolderName, i.FolderID
        FROM ImageIndexes ix
        JOIN IndexTypes it ON ix.IndexTypeID = it.IndexTypeID
        JOIN Images i ON ix.ImageID = i.ImageID
        JOIN Folders f ON i.FolderID = f.FolderID
        WHERE ix.IndexValue LIKE ?
        ORDER BY ix.IndexValue
        """,
        f"{q}%",
    )

    results: list[SearchResult] = []
    for row in cursor.fetchall():
        matched_field = "drawing_number" if row.IndexTypeName == "Drawing #" else "keyword"
        results.append(
            SearchResult(
                id=row.ImageID,
                type="image",
                file_name=row.IndexValue,
                matched_field=matched_field,
                matched_value=row.IndexValue,
                folder_name=row.FolderName,
                folder_id=row.FolderID,
                drawing_numbers=[row.IndexValue] if matched_field == "drawing_number" else [],
                keywords=[row.IndexValue] if matched_field == "keyword" else [],
            )
        )
    return results
