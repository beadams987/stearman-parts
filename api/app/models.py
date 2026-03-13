"""Pydantic response models for the Stearman Parts API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ── Folders ───────────────────────────────────────────────────────────

class FolderResponse(BaseModel):
    id: int
    name: str
    folder_name: str | None = None
    parent_id: int | None = None
    children_count: int = 0
    image_count: int = 0


# ── Images ────────────────────────────────────────────────────────────

class ImageResponse(BaseModel):
    id: int
    folder_id: int
    bundle_id: int | None = None
    bundle_offset: int | None = None
    position: int
    filename: str | None = None
    thumbnail_url: str | None = None
    width: int | None = None
    height: int | None = None
    drawing_numbers: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class ImageDetailResponse(ImageResponse):
    blob_url: str | None = None
    notes: str | None = None
    source_disc: int | None = None
    source_image_id: int | None = None
    created_at: datetime | None = None


# ── Bundles ───────────────────────────────────────────────────────────

class BundleResponse(BaseModel):
    id: int
    folder_id: int
    position: int
    page_count: int = 0
    pages: list[ImageResponse] = Field(default_factory=list)


# ── Search ────────────────────────────────────────────────────────────

class SearchResult(BaseModel):
    """Search result matching the frontend SearchResult interface."""
    id: int | str
    type: str = "image"  # 'image' | 'bundle'
    file_name: str | None = None
    thumbnail_url: str | None = None
    folder_name: str | None = None
    folder_id: int | None = None
    matched_field: str | None = None  # 'drawing_number' | 'keyword'
    matched_value: str | None = None
    drawing_numbers: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    bundle_id: int | None = None
    page_count: int | None = None


class SearchResponse(BaseModel):
    """Search response matching the frontend SearchResponse interface."""
    results: list[SearchResult] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
    total_pages: int = 1
    query: str = ""


# ── Pagination ────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[Any] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
