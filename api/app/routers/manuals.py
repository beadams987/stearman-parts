"""Manual PDF library — list, search, and page-level access."""

from __future__ import annotations

import urllib.parse
from typing import Annotated

import pyodbc
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.database import get_db
from app.services.blob_service import BlobService

router = APIRouter(prefix="/api/manuals", tags=["manuals"])

GOOGLE_VIEWER = "https://docs.google.com/viewer?url={url}&embedded=true"


# ── Models ────────────────────────────────────────────────────────────

class ManualInfo(BaseModel):
    id: str
    title: str
    description: str
    category: str
    filename: str
    size_mb: int
    page_count: int = 0


class ManualWithUrls(ManualInfo):
    download_url: str
    view_url: str


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


# ── Manual Catalog ────────────────────────────────────────────────────

MANUALS: list[ManualInfo] = [
    ManualInfo(
        id="erection-maintenance",
        title="Erection & Maintenance Instructions",
        description="Complete erection, rigging, and maintenance procedures for Army Model PT-13D and Navy Model N2S-5 aircraft.",
        category="Maintenance",
        filename="Stearman_Erection_and_Maintenance_Instructions_PT-13D_N2S-5.pdf",
        size_mb=23,
        page_count=0,
    ),
    ManualInfo(
        id="parts-catalog",
        title="Parts Catalog",
        description="Illustrated parts breakdown and part number reference for Army Model PT-13D and Navy Model N2S-5 aircraft.",
        category="Parts",
        filename="Stearman_Parts_Catalog_PT-13D_N2S-5.pdf",
        size_mb=149,
        page_count=0,
    ),
]

_MANUALS_BY_ID = {m.id: m for m in MANUALS}


# ── Helpers ───────────────────────────────────────────────────────────

def _get_blob_service(settings: Settings) -> BlobService:
    return BlobService(
        settings.AZURE_BLOB_CONNECTION_STRING,
        settings.BLOB_MANUALS_CONTAINER_NAME,
    )


def _make_sas_url(settings: Settings, filename: str) -> str:
    return _get_blob_service(settings).get_blob_url(filename, expiry_hours=2)


def _make_view_url(sas_url: str, page: int | None = None) -> str:
    encoded = urllib.parse.quote(sas_url, safe="")
    url = GOOGLE_VIEWER.format(url=encoded)
    if page is not None:
        url += f"#page={page}"
    return url


def _enrich_manual(manual: ManualInfo, settings: Settings) -> ManualWithUrls:
    sas_url = _make_sas_url(settings, manual.filename)
    return ManualWithUrls(
        **manual.model_dump(),
        download_url=sas_url,
        view_url=_make_view_url(sas_url),
    )


def _snippet(text: str, query: str, context_chars: int = 120) -> str:
    """Extract a snippet around the first query match in text."""
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

@router.get("", response_model=list[ManualWithUrls])
async def list_manuals(
    settings: Annotated[Settings, Depends(get_settings)],
    category: str | None = Query(default=None, description="Filter by category"),
) -> list[ManualWithUrls]:
    """Return all manuals with download and viewer URLs."""
    manuals = MANUALS
    if category:
        manuals = [m for m in manuals if m.category.lower() == category.lower()]
    return [_enrich_manual(m, settings) for m in manuals]


@router.get("/categories", response_model=list[str])
async def list_categories() -> list[str]:
    """Return distinct manual categories."""
    return sorted(set(m.category for m in MANUALS))


@router.get("/search", response_model=ManualSearchResponse)
async def search_manuals(
    conn: Annotated[pyodbc.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    q: str = Query(..., min_length=2, description="Search query"),
    manual_id: str | None = Query(default=None, description="Limit to specific manual"),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ManualSearchResponse:
    """Search within manual page text. Returns matching pages with snippets."""
    cursor = conn.cursor()

    # Check if ManualPages table exists
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

    # Count total matches
    cursor.execute(f"SELECT COUNT(*) FROM ManualPages mp WHERE {where}", *params)
    total: int = cursor.fetchone()[0]

    # Fetch results
    cursor.execute(
        f"""
        SELECT mp.ManualID, mp.PageNumber, mp.PageText
        FROM ManualPages mp
        WHERE {where}
        ORDER BY mp.ManualID, mp.PageNumber
        OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY
        """,
        *params,
        page_size,
    )

    results: list[ManualPageResult] = []
    for row in cursor.fetchall():
        # Find the manual metadata
        # ManualID in DB is filename-based; match against catalog
        manual = None
        for m in MANUALS:
            if m.id in row.ManualID.lower() or row.ManualID in m.filename:
                manual = m
                break
        manual_title = manual.title if manual else row.ManualID

        # Build viewer URL with page number
        if manual:
            sas_url = _make_sas_url(settings, manual.filename)
            view_url = _make_view_url(sas_url, page=row.PageNumber)
        else:
            view_url = ""

        results.append(ManualPageResult(
            manual_id=row.ManualID,
            manual_title=manual_title,
            page_number=row.PageNumber,
            snippet=_snippet(row.PageText, q),
            view_url=view_url,
        ))

    return ManualSearchResponse(results=results, total=total, query=q)


@router.get("/{manual_id}/download")
async def download_manual(
    manual_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RedirectResponse:
    """Redirect to a time-limited SAS URL for the manual PDF."""
    manual = _MANUALS_BY_ID.get(manual_id)
    if not manual:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Manual '{manual_id}' not found",
        )
    url = _make_sas_url(settings, manual.filename)
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get("/{manual_id}/view")
async def view_manual(
    manual_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    page: int | None = Query(default=None, description="Jump to page number"),
) -> RedirectResponse:
    """Redirect to Google Docs Viewer for inline PDF viewing."""
    manual = _MANUALS_BY_ID.get(manual_id)
    if not manual:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Manual '{manual_id}' not found",
        )
    sas_url = _make_sas_url(settings, manual.filename)
    view_url = _make_view_url(sas_url, page=page)
    return RedirectResponse(url=view_url, status_code=status.HTTP_302_FOUND)
