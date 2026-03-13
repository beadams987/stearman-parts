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
    """Matches frontend Image interface."""
    id: int
    folder_id: int
    file_name: str | None = None
    image_position: int = 0
    bundle_id: int | None = None
    bundle_offset: int | None = None
    thumbnail_url: str | None = None
    drawing_numbers: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class FolderBreadcrumb(BaseModel):
    id: int
    folder_name: str


class ImageDetailResponse(ImageResponse):
    """Matches frontend ImageDetail interface."""
    image_url: str | None = None
    render_url: str | None = None  # JPEG conversion endpoint for browser viewing
    dzi_url: str | None = None
    notes: str | None = None
    folder_name: str | None = None
    folder_path: list[FolderBreadcrumb] = Field(default_factory=list)
    related_images: list[ImageResponse] = Field(default_factory=list)
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
