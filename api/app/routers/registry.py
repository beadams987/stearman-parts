"""Stearman owner directory from FAA aircraft registration database."""

from __future__ import annotations

from typing import Annotated

import pyodbc
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.database import get_db

router = APIRouter(prefix="/api/registry", tags=["registry"])


class RegistryEntry(BaseModel):
    n_number: str
    serial_number: str = ""
    manufacturer: str = ""
    model: str = ""
    year_mfr: str = ""
    owner_name: str = ""
    city: str = ""
    state: str = ""
    country: str = "US"
    cert_date: str = ""


class RegistryResponse(BaseModel):
    entries: list[RegistryEntry] = Field(default_factory=list)
    total: int = 0
    states: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)


@router.get("", response_model=RegistryResponse)
async def list_registry(
    conn: Annotated[pyodbc.Connection, Depends(get_db)],
    state: str | None = Query(default=None, description="Filter by US state (2-letter)"),
    model: str | None = Query(default=None, description="Filter by model"),
    q: str | None = Query(default=None, description="Search N-number, owner, city"),
    sort: str = Query(default="recent", description="Sort: recent, state, name"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> RegistryResponse:
    """Search the Stearman owner directory."""
    cursor = conn.cursor()

    conditions = ["1=1"]
    params: list = []

    if state:
        conditions.append("r.State = ?")
        params.append(state.upper())
    if model:
        conditions.append("r.Model LIKE ?")
        params.append(f"%{model}%")
    if q:
        conditions.append("(r.NNumber LIKE ? OR r.OwnerName LIKE ? OR r.City LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])

    where = " AND ".join(conditions)
    skip = (page - 1) * page_size

    cursor.execute(f"SELECT COUNT(*) FROM Registry r WHERE {where}", *params)
    total = cursor.fetchone()[0]

    cursor.execute(f"""
        SELECT NNumber, SerialNumber, Manufacturer, Model, YearMfr,
               OwnerName, City, State, Country, CertIssueDate
        FROM Registry r
        WHERE {where}
        ORDER BY CASE WHEN ? = 'recent' THEN r.CertIssueDate END DESC,
                 CASE WHEN ? = 'state' THEN r.State END ASC,
                 CASE WHEN ? = 'name' THEN r.OwnerName END ASC,
                 r.NNumber
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """, *params, sort, sort, sort, skip, page_size)

    entries = [
        RegistryEntry(
            n_number=row.NNumber,
            serial_number=row.SerialNumber or "",
            manufacturer=row.Manufacturer or "",
            model=row.Model or "",
            year_mfr=row.YearMfr or "",
            owner_name=row.OwnerName or "",
            city=row.City or "",
            state=row.State or "",
            country=row.Country or "US",
            cert_date=row.CertIssueDate or "",
        )
        for row in cursor.fetchall()
    ]

    # Get filter options
    cursor.execute("SELECT DISTINCT State FROM Registry WHERE State IS NOT NULL AND State != '' ORDER BY State")
    states = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT Model FROM Registry WHERE Model IS NOT NULL ORDER BY Model")
    models = [row[0] for row in cursor.fetchall()]

    return RegistryResponse(entries=entries, total=total, states=states, models=models)


@router.get("/stats")
async def registry_stats(
    conn: Annotated[pyodbc.Connection, Depends(get_db)],
) -> dict:
    """Quick stats for the registry."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM Registry")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT State) FROM Registry WHERE State IS NOT NULL")
    states = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT Model) FROM Registry")
    models = cursor.fetchone()[0]
    return {"total_aircraft": total, "states": states, "models": models}
