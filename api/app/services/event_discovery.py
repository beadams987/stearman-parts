"""Event discovery service — searches for Stearman events via Gemini AI.

Called by Azure Functions timer trigger. Runs entirely in Azure cloud:
Azure Timer → Gemini API (with Google Search grounding) → Azure SQL.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
from datetime import datetime

import pyodbc

log = logging.getLogger(__name__)

SEARCH_QUERIES = [
    "Stearman biplane airshow fly-in events 2026 2027 upcoming schedule",
    "Boeing Kaydet PT-17 formation flight event 2026 2027",
    "Stearman Restorers Association annual fly-in 2026 2027",
    "vintage warbird airshow featuring Stearman biplane 2026 2027",
    "Stearman biplane museum exhibit event worldwide 2026 2027",
    "airshow schedule 2026 2027 Stearman Kaydet confirmed aircraft",
    "EAA fly-in warbird event Stearman PT-17 N2S biplane",
    "Stearman biplane rides event open cockpit 2026 2027",
    "AOPA fly-in regional airshow biplane Stearman Kaydet",
    "vintage aircraft airshow Stearman Kaydet PT-13 PT-18 2026 2027",
    "Reno air races warbird Stearman 2026",
    "Reading airshow Mid-Atlantic warbird Stearman 2026 2027",
    "Wings Over airshow Stearman biplane 2026 2027",
    "Commemorative Air Force Stearman event ride 2026 2027",
]

EXTRACT_PROMPT = """Based on the search results, extract ALL upcoming events featuring Boeing-Stearman (Kaydet, PT-13, PT-17, PT-18, N2S) aircraft.

Return a JSON array. Each object must have:
- title: event name
- description: brief description (prefer organizer's words, NOT your summary)
- event_type: airshow | fly-in | museum | formation | restoration | gathering | other
- start_date: YYYY-MM-DD
- end_date: YYYY-MM-DD or null
- city, state_province, country
- venue: airport or venue name
- url: official event website (NOT search engine URL)
- featured_aircraft: array of aircraft types

Only include events with confirmed dates. Return ONLY JSON array, no markdown."""


def discover_events(gemini_api_key: str, sql_connection_string: str) -> dict:
    """Search for events and store in database. Returns summary stats."""
    conn = pyodbc.connect(sql_connection_string, autocommit=False)
    _ensure_table(conn)

    total_new = 0
    total_updated = 0
    errors = []

    for i, query in enumerate(SEARCH_QUERIES):
        log.info("Search %d/%d: %s", i + 1, len(SEARCH_QUERIES), query)
        try:
            response = _search_gemini(query, gemini_api_key)
            if not response:
                continue

            events = _parse_events(response)
            log.info("  Found %d events", len(events))

            for event in events:
                result = _store_event(conn, event)
                if result == "new":
                    total_new += 1
                elif result == "updated":
                    total_updated += 1
        except Exception as e:
            log.error("Search %d failed: %s", i + 1, e)
            errors.append(str(e))

        time.sleep(2)  # Rate limit between searches

    # Auto-populate recurring annual events for next year
    recurring_new = _populate_recurring_events(conn)
    total_new += recurring_new

    conn.close()
    return {"new": total_new, "updated": total_updated, "errors": errors}


# Annual recurring events — auto-populated with estimated dates
RECURRING_EVENTS = [
    {
        "title_pattern": "National Stearman Fly-In",
        "title_template": "{nth} National Stearman Fly-In ({year})",
        "description": "Annual gathering of Boeing Stearman biplanes. Week-long event with formation flying, contests, seminars, and the SRA Annual Meeting.",
        "event_type": "fly-in",
        "month": 9, "day": 7, "duration_days": 5,  # First week of September
        "city": "Galesburg", "state": "IL", "country": "USA",
        "venue": "Galesburg Municipal Airport (KGBG)",
        "url": "https://www.stearmanflyin.com",
        "aircraft": ["Stearman PT-17", "Stearman N2S", "Boeing Model 75"],
        "base_year": 2026, "base_nth": 55,
    },
    {
        "title_pattern": "EAA AirVenture Oshkosh",
        "title_template": "EAA AirVenture Oshkosh {year}",
        "description": "The world's greatest aviation celebration. Stearmans are regular fixtures in the vintage/warbird areas.",
        "event_type": "airshow",
        "month": 7, "day": 26, "duration_days": 6,  # Last week of July
        "city": "Oshkosh", "state": "WI", "country": "USA",
        "venue": "Wittman Regional Airport (KOSH)",
        "url": "https://www.eaa.org/airventure",
        "aircraft": ["Various Stearman models"],
        "base_year": 2026, "base_nth": 0,
    },
    {
        "title_pattern": "Sun 'n Fun Aerospace Expo",
        "title_template": "Sun 'n Fun Aerospace Expo {year}",
        "description": "Major annual fly-in and air show. Stearman biplanes regularly appear.",
        "event_type": "airshow",
        "month": 3, "day": 30, "duration_days": 5,  # Late March
        "city": "Lakeland", "state": "FL", "country": "USA",
        "venue": "Lakeland Linder International Airport (KLAL)",
        "url": "https://www.flysnf.org",
        "aircraft": ["Various Stearman models"],
        "base_year": 2027, "base_nth": 0,
    },
]


def _populate_recurring_events(conn: pyodbc.Connection) -> int:
    """Auto-populate recurring annual events for the next 18 months."""
    import json as _json
    from datetime import timedelta

    cur = conn.cursor()
    now = datetime.now()
    cutoff = now + timedelta(days=548)  # ~18 months
    new_count = 0

    for event in RECURRING_EVENTS:
        for year in [now.year, now.year + 1]:
            start = datetime(year, event["month"], event["day"])
            if start < now - timedelta(days=2) or start > cutoff:
                continue

            end = start + timedelta(days=event["duration_days"])
            nth = event["base_nth"] + (year - event["base_year"]) if event["base_nth"] else 0
            ordinals = {1: "1st", 2: "2nd", 3: "3rd"}
            nth_str = ordinals.get(nth % 10, f"{nth}th") if nth else ""
            title = event["title_template"].format(year=year, nth=nth_str)

            location = f"{event['city']}, {event['state']}, {event['country']}"

            # Check if already exists
            cur.execute("SELECT COUNT(*) FROM Events WHERE Title LIKE ? AND YEAR(StartDate) = ?",
                        f"%{event['title_pattern']}%{year}%", year)
            if cur.fetchone()[0] > 0:
                continue

            try:
                cur.execute("""
                    INSERT INTO Events (Title, Description, EventType, StartDate, EndDate,
                        Location, City, StateProvince, Country, Venue, EventURL, Source,
                        FeaturedAircraft, DateEstimated, Status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Annual recurring event', ?, 1, 'upcoming')
                """,
                    title, event["description"], event["event_type"],
                    start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"),
                    location, event["city"], event["state"], event["country"],
                    event["venue"], event["url"], _json.dumps(event["aircraft"]),
                )
                conn.commit()
                new_count += 1
                log.info("  Added recurring: %s", title)
            except Exception as e:
                log.warning("  Recurring event skip: %s — %s", title, e)
                conn.rollback()

    return new_count


def purge_past_events(sql_connection_string: str) -> int:
    """Delete events that ended more than 48 hours ago. Returns count deleted."""
    conn = pyodbc.connect(sql_connection_string, autocommit=True)
    _ensure_table(conn)
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM Events
        WHERE COALESCE(EndDate, StartDate) < DATEADD(hour, -48, GETUTCDATE())
    """)
    deleted = cur.rowcount
    log.info("Purged %d past events", deleted)
    conn.close()
    return deleted


def _ensure_table(conn: pyodbc.Connection) -> None:
    cur = conn.cursor()
    cur.execute("""
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


def _search_gemini(query: str, api_key: str) -> str:
    """Search web via Gemini with Google Search grounding."""
    # Try 2.5-flash first (has search grounding), fall back to flash-lite
    for model in ["gemini-2.5-flash", "gemini-2.5-flash-lite"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        if model == "gemini-2.5-flash":
            payload = json.dumps({
                "contents": [{"parts": [{"text": f"Search: {query}\n\n{EXTRACT_PROMPT}"}]}],
                "tools": [{"google_search": {}}],
            }).encode()
        else:
            # Flash-lite doesn't support search grounding — use knowledge only
            payload = json.dumps({
                "contents": [{"parts": [{"text": f"Based on your knowledge of upcoming aviation events, {query}\n\n{EXTRACT_PROMPT}"}]}],
            }).encode()

        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=45).read())
            text = resp["candidates"][0]["content"]["parts"][-1]["text"]
            return text.strip()
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                log.warning("Model %s unavailable (%d), trying next...", model, e.code)
                continue
            elif e.code == 400:
                log.warning("Model %s returned 400, trying next...", model)
                continue
            else:
                raise
        except Exception as e:
            log.warning("Model %s failed: %s, trying next...", model, e)
            continue

    return ""


def _parse_events(response_text: str) -> list[dict]:
    text = response_text.strip()
    text = re.sub(r"^```json?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        events = json.loads(text)
        if isinstance(events, list):
            return events
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return []


def _store_event(conn: pyodbc.Connection, event: dict) -> str:
    """Store or update an event. Returns 'new', 'updated', or 'skipped'."""
    cur = conn.cursor()
    title = event.get("title", "").strip()
    start_date = event.get("start_date", "")
    event_url = event.get("url", "").strip()

    if not title or not start_date or not event_url:
        return "skipped"

    try:
        datetime.strptime(start_date, "%Y-%m-%d")
    except ValueError:
        return "skipped"

    location = event.get("location", "") or f"{event.get('city', '')}, {event.get('state_province', '')}, {event.get('country', '')}".strip(", ")
    aircraft_json = json.dumps(event.get("featured_aircraft", []))
    end_date = event.get("end_date")
    if end_date == "null" or not end_date:
        end_date = None

    try:
        # Check if exists
        cur.execute("SELECT EventID FROM Events WHERE Title = ? AND StartDate = ?", title, start_date)
        existing = cur.fetchone()

        if existing:
            cur.execute("""
                UPDATE Events SET LastVerifiedAt = GETUTCDATE(),
                    Description = COALESCE(?, Description),
                    EventURL = COALESCE(?, EventURL)
                WHERE EventID = ?
            """, event.get("description", ""), event_url, existing[0])
            conn.commit()
            return "updated"
        else:
            cur.execute("""
                INSERT INTO Events (Title, Description, EventType, StartDate, EndDate, Location,
                    City, StateProvince, Country, Venue, EventURL, Source, FeaturedAircraft, Status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'upcoming')
            """,
                title, event.get("description", "")[:4000], event.get("event_type", "other"),
                start_date, end_date, location,
                event.get("city", ""), event.get("state_province", ""), event.get("country", ""),
                event.get("venue", ""), event_url, event.get("source", ""), aircraft_json,
            )
            conn.commit()
            return "new"
    except pyodbc.IntegrityError:
        conn.rollback()
        return "skipped"
    except Exception as e:
        log.error("Store event failed: %s", e)
        conn.rollback()
        return "skipped"
