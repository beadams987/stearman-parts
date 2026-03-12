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
    id: int | str
    entity_type: str | None = None
    title: str | None = None
    drawing_number: str | None = None
    keyword: str | None = None
    folder_name: str | None = None
    thumbnail_url: str | None = None


class SearchResponse(BaseModel):
    results: list[SearchResult] = Field(default_factory=list)
    total_count: int = 0
    query: str = ""


# ── Pagination ────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[Any] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
