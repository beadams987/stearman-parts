"""Stearman events — upcoming airshows, fly-ins, and gatherings worldwide."""

from __future__ import annotations

from typing import Annotated

import pyodbc
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.database import get_db

router = APIRouter(prefix="/api/events", tags=["events"])


class Event(BaseModel):
    id: int
    title: str
    description: str
    event_type: str  # airshow, fly-in, museum, formation, restoration, other
    start_date: str  # ISO date
    end_date: str | None = None
    location: str
    city: str = ""
    state_province: str = ""
    country: str = ""
    venue: str = ""
    url: str  # authoritative event link
    source: str = ""  # where we found it
    ai_summary: str = ""  # only if no good description from organizer
    featured_aircraft: list[str] = Field(default_factory=list)
    image_url: str = ""
    status: str = "upcoming"  # upcoming, ongoing, past, cancelled


class EventsResponse(BaseModel):
    events: list[Event] = Field(default_factory=list)
    total: int = 0


@router.get("", response_model=EventsResponse)
async def list_events(
    conn: Annotated[pyodbc.Connection, Depends(get_db)],
    event_type: str | None = Query(default=None),
    country: str | None = Query(default=None),
    upcoming_only: bool = Query(default=True),
    page_size: int = Query(default=50, ge=1, le=200),
) -> EventsResponse:
    """List Stearman-related events with optional filters."""
    cursor = conn.cursor()

    # Ensure table exists
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Events' AND xtype='U')
        CREATE TABLE Events (
            EventID INT IDENTITY PRIMARY KEY,
            Title NVARCHAR(500) NOT NULL,
            Description NVARCHAR(MAX),
            EventType NVARCHAR(50),
            StartDate DATE NOT NULL,
            EndDate DATE,
            Location NVARCHAR(500),
            City NVARCHAR(200),
            StateProvince NVARCHAR(200),
            Country NVARCHAR(100),
            Venue NVARCHAR(500),
            EventURL NVARCHAR(2000) NOT NULL,
            Source NVARCHAR(500),
            AiSummary NVARCHAR(MAX),
            FeaturedAircraft NVARCHAR(MAX),
            ImageURL NVARCHAR(2000),
            Status NVARCHAR(20) DEFAULT 'upcoming',
            DiscoveredAt DATETIME2 DEFAULT GETUTCDATE(),
            LastVerifiedAt DATETIME2,
            UNIQUE (Title, StartDate, Location)
        )
    """)

    conditions = ["1=1"]
    params: list = []

    if upcoming_only:
        conditions.append("e.StartDate >= CAST(GETDATE() AS DATE)")
    if event_type:
        conditions.append("e.EventType = ?")
        params.append(event_type)
    if country:
        conditions.append("e.Country LIKE ?")
        params.append(f"%{country}%")

    where = " AND ".join(conditions)

    cursor.execute(f"""
        SELECT COUNT(*) FROM Events e WHERE {where}
    """, *params)
    total = cursor.fetchone()[0]

    cursor.execute(f"""
        SELECT EventID, Title, Description, EventType, StartDate, EndDate,
               Location, City, StateProvince, Country, Venue, EventURL,
               Source, AiSummary, FeaturedAircraft, ImageURL, Status
        FROM Events e
        WHERE {where}
        ORDER BY e.StartDate ASC
        OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY
    """, *params, page_size)

    events = []
    for row in cursor.fetchall():
        aircraft = []
        if row.FeaturedAircraft:
            try:
                import json
                aircraft = json.loads(row.FeaturedAircraft)
            except Exception:
                aircraft = [a.strip() for a in row.FeaturedAircraft.split(",") if a.strip()]

        events.append(Event(
            id=row.EventID,
            title=row.Title,
            description=row.Description or "",
            event_type=row.EventType or "other",
            start_date=str(row.StartDate),
            end_date=str(row.EndDate) if row.EndDate else None,
            location=row.Location or "",
            city=row.City or "",
            state_province=row.StateProvince or "",
            country=row.Country or "",
            venue=row.Venue or "",
            url=row.EventURL,
            source=row.Source or "",
            ai_summary=row.AiSummary or "",
            featured_aircraft=aircraft,
            image_url=row.ImageURL or "",
            status=row.Status or "upcoming",
        ))

    return EventsResponse(events=events, total=total)


@router.get("/types", response_model=list[str])
async def list_event_types(
    conn: Annotated[pyodbc.Connection, Depends(get_db)],
) -> list[str]:
    """Return distinct event types."""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT EventType FROM Events WHERE EventType IS NOT NULL ORDER BY EventType")
        return [row[0] for row in cursor.fetchall()]
    except Exception:
        return []
