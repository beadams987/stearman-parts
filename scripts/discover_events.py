#!/usr/bin/env python3
"""Discover upcoming Stearman/Kaydet events worldwide using Gemini AI search.

Searches for airshows, fly-ins, museum events, formation flights, and
restoration gatherings featuring Boeing-Stearman aircraft. Stores results
in the Events table for display on the website.

Usage:
    python discover_events.py                # Full discovery run
    python discover_events.py --dry-run      # Preview without DB writes
    python discover_events.py --verify       # Re-verify existing events

Environment:
    GEMINI_API_KEY
    AZURE_SQL_CONNECTION_STRING
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

import pyodbc

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SEARCH_QUERIES = [
    "Stearman biplane airshow 2026 upcoming events",
    "Stearman fly-in 2026 schedule",
    "Boeing Stearman Kaydet formation flight event 2026",
    "PT-17 Stearman museum event exhibit 2026",
    "vintage biplane airshow Stearman 2026 2027",
    "Stearman Restorers Association annual fly-in",
    "warbird airshow Stearman Kaydet schedule",
    "Stearman gathering aviation event worldwide",
]

GEMINI_EXTRACT_PROMPT = """You searched the web for Stearman biplane events. Based on the search results, extract all upcoming events featuring Boeing-Stearman (Kaydet, PT-13, PT-17, PT-18, N2S) aircraft.

For each event, provide a JSON array of objects with these fields:
- title: event name
- description: brief description from the event organizer (use their words if available, NOT your summary)
- event_type: one of [airshow, fly-in, museum, formation, restoration, gathering, other]
- start_date: YYYY-MM-DD format
- end_date: YYYY-MM-DD or null
- location: "City, State/Province, Country"
- city: city name
- state_province: state or province
- country: country name
- venue: venue/airport name if known
- url: the authoritative event website URL (NOT a search result URL)
- source: where you found this info
- featured_aircraft: array of aircraft types mentioned (e.g. ["Stearman PT-17", "N2S-3"])
- ai_summary: ONLY provide this if the organizer's description is missing or too long. Keep under 150 words.

IMPORTANT:
- Only include events with CONFIRMED dates (not "TBD")
- Only include events where Stearman/Kaydet aircraft are specifically mentioned or highly likely to appear
- Prefer the event organizer's own description over your summary
- URLs must point to the actual event page, not search engines
- Include events worldwide, not just US

Return ONLY a JSON array. No markdown, no explanation."""


def search_with_gemini(query: str, api_key: str) -> str:
    """Use Gemini with grounding/search to find events."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    payload = json.dumps({
        "contents": [{"parts": [{"text": f"Search the web for: {query}\n\nThen: {GEMINI_EXTRACT_PROMPT}"}]}],
        "tools": [{"google_search": {}}],
    }).encode()

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

    for attempt in range(3):
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
            text = resp["candidates"][0]["content"]["parts"][-1]["text"]
            return text.strip()
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                wait = 15 * (attempt + 1)
                log.warning("Rate limited/unavailable, waiting %ds...", wait)
                time.sleep(wait)
            else:
                log.error("Gemini error %d: %s", e.code, e.read().decode()[:200])
                return ""
        except Exception as e:
            log.error("Search error: %s", e)
            if attempt < 2:
                time.sleep(5)
    return ""


def parse_events(response_text: str) -> list[dict]:
    """Parse JSON events from Gemini response."""
    # Try to find JSON array in the response
    text = response_text.strip()

    # Remove markdown code fences if present
    text = re.sub(r"^```json?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        events = json.loads(text)
        if isinstance(events, list):
            return events
    except json.JSONDecodeError:
        # Try to find JSON array within the text
        match = re.search(r"\[[\s\S]*\]", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

    log.warning("Could not parse events from response (length %d)", len(text))
    return []


def store_events(conn: pyodbc.Connection, events: list[dict], dry_run: bool = False) -> int:
    """Store discovered events in the database. Returns count of new events."""
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
    conn.commit()

    new_count = 0
    for event in events:
        title = event.get("title", "").strip()
        start_date = event.get("start_date", "")
        location = event.get("location", "").strip()
        event_url = event.get("url", "").strip()

        if not title or not start_date or not event_url:
            continue

        # Validate date format
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            log.warning("Skipping event with bad date: %s (%s)", title, start_date)
            continue

        if dry_run:
            log.info("  DRY RUN: %s | %s | %s | %s", title, start_date, location, event_url)
            new_count += 1
            continue

        try:
            aircraft_json = json.dumps(event.get("featured_aircraft", []))
            end_date = event.get("end_date")

            cursor.execute("""
                MERGE Events AS target
                USING (SELECT ? AS Title, ? AS StartDate, ? AS Location) AS source
                ON target.Title = source.Title AND target.StartDate = source.StartDate
                WHEN NOT MATCHED THEN INSERT
                    (Title, Description, EventType, StartDate, EndDate, Location, City,
                     StateProvince, Country, Venue, EventURL, Source, AiSummary,
                     FeaturedAircraft, Status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'upcoming')
                WHEN MATCHED THEN UPDATE SET
                    LastVerifiedAt = GETUTCDATE(),
                    Description = COALESCE(?, target.Description),
                    EventURL = COALESCE(?, target.EventURL);
            """,
                title, start_date, location,
                title,
                event.get("description", "")[:4000],
                event.get("event_type", "other"),
                start_date,
                end_date if end_date and end_date != "null" else None,
                location,
                event.get("city", ""),
                event.get("state_province", ""),
                event.get("country", ""),
                event.get("venue", ""),
                event_url,
                event.get("source", ""),
                event.get("ai_summary", ""),
                aircraft_json,
                event.get("description", "")[:4000],
                event_url,
            )
            conn.commit()
            new_count += 1
        except pyodbc.IntegrityError:
            conn.rollback()
        except Exception as e:
            log.error("Failed to store event '%s': %s", title, e)
            conn.rollback()

    return new_count


def main():
    parser = argparse.ArgumentParser(description="Discover Stearman events")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify", action="store_true", help="Re-verify existing events")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not set")
        sys.exit(1)

    conn = pyodbc.connect(os.environ["AZURE_SQL_CONNECTION_STRING"], autocommit=False)

    total_events = 0
    for i, query in enumerate(SEARCH_QUERIES):
        log.info("Search %d/%d: %s", i + 1, len(SEARCH_QUERIES), query)

        response = search_with_gemini(query, api_key)
        if not response:
            continue

        events = parse_events(response)
        log.info("  Found %d events", len(events))

        new = store_events(conn, events, dry_run=args.dry_run)
        total_events += new

        # Rate limit between searches
        time.sleep(3)

    log.info("Discovery complete: %d events found/updated", total_events)

    # Show summary
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM Events WHERE StartDate >= CAST(GETDATE() AS DATE)")
        upcoming = cursor.fetchone()[0]
        log.info("Total upcoming events in database: %d", upcoming)
    except Exception:
        pass

    conn.close()


if __name__ == "__main__":
    main()
