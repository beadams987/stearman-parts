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


def _extract_ocr_snippet(ocr_text: str, query: str, max_len: int = 150) -> str | None:
    """Extract a short snippet around the first occurrence of *query* in *ocr_text*."""
    if not ocr_text or not query:
        return None
    lower = ocr_text.lower()
    idx = lower.find(query.lower())
    if idx == -1:
        return None
    start = max(0, idx - 60)
    end = min(len(ocr_text), idx + len(query) + 60)
    snippet = ocr_text[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(ocr_text):
        snippet = snippet + "..."
    return snippet[:max_len]


def _resolve_thumb_url(path: str | None, thumbs_svc: BlobService | None) -> str | None:
    """Generate a SAS-signed thumbnail URL if possible; fall back to raw path."""
    if not path:
        return None
    if thumbs_svc is not None:
        try:
            return thumbs_svc.get_thumbnail_url(path)
        except Exception:
            return path
    return path


def _sql_ocr_search(
    cursor: pyodbc.Cursor,
    query: str,
    *,
    folder_id: int | None = None,
    top: int = 50,
    skip: int = 0,
    thumbs_svc: BlobService | None = None,
    exclude_image_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Search only the OcrText column."""
    conditions = ["i.OcrText LIKE ?"]
    params: list[Any] = [f"%{query}%"]

    if folder_id is not None:
        conditions.append("i.FolderID = ?")
        params.append(folder_id)

    if exclude_image_ids:
        placeholders = ",".join("?" for _ in exclude_image_ids)
        conditions.append(f"i.ImageID NOT IN ({placeholders})")
        params.extend(exclude_image_ids)

    where = " AND ".join(conditions)

    cursor.execute(f"SELECT COUNT(*) FROM Images i WHERE {where}", *params)
    total_count: int = cursor.fetchone()[0]

    search_sql = f"""
        SELECT i.ImageID, i.OriginalFileName, i.ThumbnailPath, i.FolderID,
               f.FolderName, i.BundleID, i.OcrText
        FROM Images i
        JOIN Folders f ON i.FolderID = f.FolderID
        WHERE {where}
        ORDER BY i.ImageID
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """
    cursor.execute(search_sql, *params, skip, top)

    results: list[dict[str, Any]] = []
    for row in cursor.fetchall():
        ocr_snippet = _extract_ocr_snippet(row.OcrText, query)
        results.append({
            "id": row.ImageID,
            "type": "image",
            "file_name": row.OriginalFileName,
            "thumbnail_url": _resolve_thumb_url(row.ThumbnailPath, thumbs_svc),
            "folder_name": row.FolderName,
            "folder_id": row.FolderID,
            "matched_field": "ocr_text",
            "matched_value": ocr_snippet or query,
            "drawing_numbers": [],
            "keywords": [],
            "bundle_id": row.BundleID,
            "page_count": None,
            "ocr_snippet": ocr_snippet,
        })

    return {"results": results, "total_count": total_count}


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

    # OCR-only search: search the OcrText column directly
    if index_type == "ocr":
        return _sql_ocr_search(
            cursor, query, folder_id=folder_id, top=top, skip=skip, thumbs_svc=thumbs_svc,
        )

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

    # Count total matches
    count_sql = f"""
        SELECT COUNT(DISTINCT i.ImageID)
        FROM ImageIndexes ix
        JOIN IndexTypes it ON ix.IndexTypeID = it.IndexTypeID
        JOIN Images i ON ix.ImageID = i.ImageID
        WHERE {where}
    """
    cursor.execute(count_sql, *params)
    total_count: int = cursor.fetchone()[0]

    # Fetch page of results — group by image, aggregate index values
    search_sql = f"""
        SELECT i.ImageID, i.OriginalFileName, i.ThumbnailPath, i.FolderID,
               ix.IndexValue, it.Name AS IndexTypeName,
               f.FolderName, i.BundleID, i.OcrText
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
    seen_ids: list[int] = []
    for row in cursor.fetchall():
        index_type_name = row.IndexTypeName
        matched_field = "drawing_number" if index_type_name == "Drawing #" else "keyword"

        drawing_numbers: list[str] = []
        keywords: list[str] = []
        if index_type_name == "Drawing #":
            drawing_numbers.append(row.IndexValue)
        else:
            keywords.append(row.IndexValue)

        ocr_snippet = _extract_ocr_snippet(row.OcrText, query) if row.OcrText else None

        results.append({
            "id": row.ImageID,
            "type": "image",
            "file_name": row.OriginalFileName,
            "thumbnail_url": _resolve_thumb_url(row.ThumbnailPath, thumbs_svc),
            "folder_name": row.FolderName,
            "folder_id": row.FolderID,
            "matched_field": matched_field,
            "matched_value": row.IndexValue,
            "drawing_numbers": drawing_numbers,
            "keywords": keywords,
            "bundle_id": row.BundleID,
            "page_count": None,
            "ocr_snippet": ocr_snippet,
        })
        seen_ids.append(row.ImageID)

    # If we have room and no specific type filter, add OCR-only matches
    remaining = top - len(results)
    if remaining > 0 and not index_type:
        ocr_data = _sql_ocr_search(
            cursor, query, folder_id=folder_id, top=remaining, skip=0,
            thumbs_svc=thumbs_svc, exclude_image_ids=seen_ids,
        )
        results.extend(ocr_data["results"])
        total_count += ocr_data["total_count"]

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
