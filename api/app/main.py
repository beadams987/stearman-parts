"""Stearman Parts API -- FastAPI application entry point."""

from typing import Annotated

import pyodbc
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import get_db
from app.routers import bundles, deploy, events, folders, images, manuals, search, submissions

app = FastAPI(
    title="Stearman Parts API",
    description="Boeing-Stearman aircraft engineering drawings and service manual API.",
    version="0.1.0",
)

# ── CORS ──────────────────────────────────────────────────────────────

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────

app.include_router(folders.router)
app.include_router(images.router)
app.include_router(bundles.router)
app.include_router(search.router)
app.include_router(deploy.router)
app.include_router(manuals.router)
app.include_router(submissions.router)
app.include_router(events.router)


# ── Health check ──────────────────────────────────────────────────────

@app.get("/api/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Liveness probe with commit SHA for deploy verification."""
    import os
    return {
        "status": "ok",
        "commit": os.environ.get("DEPLOY_COMMIT", "unknown"),
    }


@app.get("/api/stats", tags=["stats"])
async def get_stats(
    conn: Annotated[pyodbc.Connection, Depends(get_db)],
) -> dict[str, int]:
    """Return aggregate stats for the home page."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM Images")
    total_images = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM Folders")
    total_folders = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM Bundles")
    total_bundles = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM ImageIndexes")
    idx = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM BundleIndexes")
    bidx = cursor.fetchone()[0]
    return {
        "total_images": total_images,
        "total_folders": total_folders,
        "total_bundles": total_bundles,
        "total_indexes": idx + bidx,
    }
