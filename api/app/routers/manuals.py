"""Manuals Library API — browse, search, filter, and view the full catalog."""

from __future__ import annotations

import urllib.parse
from typing import Annotated

import pyodbc
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.catalog import ALL_ITEMS, CATEGORIES, ITEMS_BY_ID, CatalogItem
from app.config import Settings, get_settings
from app.database import get_db
from app.services.blob_service import BlobService

router = APIRouter(prefix="/api/manuals", tags=["manuals"])

GOOGLE_VIEWER = "https://docs.google.com/viewer?url={url}&embedded=true"


# ── Response Models ───────────────────────────────────────────────────

class CatalogItemResponse(BaseModel):
    id: str
    title: str
    description: str
    category: str
    subcategory: str
    content_type: str
    size_mb: float
    tags: list[str]
    source: str
    year: int | None
    models: list[str]
    download_url: str
    view_url: str


class CatalogResponse(BaseModel):
    items: list[CatalogItemResponse] = Field(default_factory=list)
    total: int = 0
    categories: list[str] = Field(default_factory=list)


class ManualPageResult(BaseModel):
    manual_id: str
    manual_title: str
    page_number: int
    snippet: str
    view_url: str


class ManualSearchResponse(BaseModel):
    results: list[ManualPageResult] = Field(default_factory=list)
    total: int = 0
    query: str = ""


# ── Helpers ───────────────────────────────────────────────────────────

def _get_blob_service(settings: Settings, container: str) -> BlobService:
    return BlobService(settings.AZURE_BLOB_CONNECTION_STRING, container)


def _make_sas_url(settings: Settings, item: CatalogItem) -> str:
    svc = _get_blob_service(settings, item.container)
    return svc.get_blob_url(item.blob_path, expiry_hours=2)


def _make_view_url(sas_url: str, page: int | None = None) -> str:
    encoded = urllib.parse.quote(sas_url, safe="")
    url = GOOGLE_VIEWER.format(url=encoded)
    if page is not None:
        url += f"#page={page}"
    return url


def _enrich_item(item: CatalogItem, settings: Settings) -> CatalogItemResponse:
    sas_url = _make_sas_url(settings, item)
    return CatalogItemResponse(
        **item.model_dump(),
        download_url=sas_url,
        view_url=_make_view_url(sas_url),
    )


def _snippet(text: str, query: str, context_chars: int = 120) -> str:
    lower = text.lower()
    idx = lower.find(query.lower())
    if idx < 0:
        return text[:context_chars * 2] + "..." if len(text) > context_chars * 2 else text
    start = max(0, idx - context_chars)
    end = min(len(text), idx + len(query) + context_chars)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


# ── Endpoints ─────────────────────────────────────────────────────────

@router.get("", response_model=CatalogResponse)
async def list_catalog(
    settings: Annotated[Settings, Depends(get_settings)],
    category: str | None = Query(default=None, description="Filter by category"),
    model: str | None = Query(default=None, description="Filter by aircraft model (e.g. PT-17)"),
    tag: str | None = Query(default=None, description="Filter by tag"),
    q: str | None = Query(default=None, description="Text search in title/description"),
) -> CatalogResponse:
    """Return the full content catalog with optional filters."""
    items = ALL_ITEMS

    if category:
        items = [i for i in items if i.category.lower() == category.lower()]
    if model:
        m = model.upper()
        items = [i for i in items if any(m in mod.upper() for mod in i.models)]
    if tag:
        t = tag.lower()
        items = [i for i in items if any(t in tg.lower() for tg in i.tags)]
    if q:
        ql = q.lower()
        items = [i for i in items if ql in i.title.lower() or ql in i.description.lower()]

    enriched = [_enrich_item(i, settings) for i in items]
    return CatalogResponse(items=enriched, total=len(enriched), categories=CATEGORIES)


@router.get("/categories", response_model=list[str])
async def list_categories() -> list[str]:
    """Return distinct content categories."""
    return CATEGORIES


@router.get("/models", response_model=list[str])
async def list_models() -> list[str]:
    """Return distinct aircraft models referenced across the catalog."""
    models = set()
    for item in ALL_ITEMS:
        models.update(item.models)
    return sorted(models)


@router.get("/tags", response_model=list[str])
async def list_tags() -> list[str]:
    """Return all distinct tags across the catalog."""
    tags = set()
    for item in ALL_ITEMS:
        tags.update(item.tags)
    return sorted(tags)


@router.get("/search", response_model=ManualSearchResponse)
async def search_manuals(
    conn: Annotated[pyodbc.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    q: str = Query(..., min_length=2, description="Search query"),
    manual_id: str | None = Query(default=None, description="Limit to specific manual"),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ManualSearchResponse:
    """Full-text search within manual page content."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_NAME = 'ManualPages'
    """)
    if cursor.fetchone()[0] == 0:
        return ManualSearchResponse(results=[], total=0, query=q)

    conditions = ["mp.PageText LIKE ?"]
    params: list = [f"%{q}%"]
    if manual_id:
        conditions.append("mp.ManualID LIKE ?")
        params.append(f"%{manual_id}%")
    where = " AND ".join(conditions)

    cursor.execute(f"SELECT COUNT(*) FROM ManualPages mp WHERE {where}", *params)
    total: int = cursor.fetchone()[0]

    cursor.execute(
        f"""SELECT mp.ManualID, mp.PageNumber, mp.PageText
            FROM ManualPages mp WHERE {where}
            ORDER BY mp.ManualID, mp.PageNumber
            OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY""",
        *params, page_size,
    )

    results: list[ManualPageResult] = []
    for row in cursor.fetchall():
        item = None
        for i in ALL_ITEMS:
            if i.id in row.ManualID.lower() or row.ManualID in i.blob_path:
                item = i
                break
        title = item.title if item else row.ManualID

        if item:
            sas_url = _make_sas_url(settings, item)
            view_url = _make_view_url(sas_url, page=row.PageNumber)
        else:
            view_url = ""

        results.append(ManualPageResult(
            manual_id=row.ManualID,
            manual_title=title,
            page_number=row.PageNumber,
            snippet=_snippet(row.PageText, q),
            view_url=view_url,
        ))

    return ManualSearchResponse(results=results, total=total, query=q)


@router.get("/{item_id}/download")
async def download_item(
    item_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RedirectResponse:
    """Redirect to a time-limited SAS URL for download."""
    item = ITEMS_BY_ID.get(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    url = _make_sas_url(settings, item)
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get("/{item_id}/view")
async def view_item(
    item_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    page: int | None = Query(default=None, description="Jump to page"),
) -> RedirectResponse:
    """Redirect to Google Docs Viewer for inline viewing."""
    item = ITEMS_BY_ID.get(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    sas_url = _make_sas_url(settings, item)
    return RedirectResponse(url=_make_view_url(sas_url, page=page), status_code=status.HTTP_302_FOUND)
