"""Analytics router — read-only aggregate stats from Azure Application Insights.

Exposes GET /api/analytics which returns pre-aggregated site usage metrics for
the analytics dashboard. No authentication is required; the endpoint deliberately
returns only aggregates (no PII, no raw events).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

APPI_BASE = "https://api.applicationinsights.io/v1/apps"
HTTP_TIMEOUT = 15.0


async def _run_query(
    client: httpx.AsyncClient, app_id: str, api_key: str, kql: str,
) -> list[list[Any]]:
    """Execute a KQL query against App Insights REST API. Returns row list or []."""
    try:
        resp = await client.post(
            f"{APPI_BASE}/{app_id}/query",
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json={"query": kql},
            timeout=HTTP_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        logger.warning("App Insights query transport error: %s", exc)
        return []

    if resp.status_code != 200:
        logger.warning(
            "App Insights query failed: %d %s — query=%s",
            resp.status_code, resp.text[:200], kql[:80],
        )
        return []

    try:
        data = resp.json()
    except ValueError:
        return []
    tables = data.get("tables") or []
    if not tables:
        return []
    return tables[0].get("rows") or []


def _first_cell(rows: list[list[Any]], default: Any = 0) -> Any:
    if rows and rows[0]:
        val = rows[0][0]
        return val if val is not None else default
    return default


@router.get("", summary="Site analytics (aggregates only)")
async def get_analytics(
    settings: Annotated[Settings, Depends(get_settings)],
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    """Return pre-aggregated analytics metrics for the dashboard.

    This endpoint is intentionally unauthenticated — it only returns aggregates
    (counts and averages), never individual events or PII. If Application
    Insights is unreachable or has no data, all numeric fields default to 0
    and all lists default to [].
    """
    api_key = settings.APPINSIGHTS_QUERY_KEY
    app_id = settings.APPINSIGHTS_APP_ID

    empty_result: dict[str, Any] = {
        "period": f"{days}d",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_visits": 0,
            "unique_visitors": 0,
            "total_pageviews": 0,
            "avg_session_duration_sec": 0,
            "bounce_rate_pct": 0,
        },
        "daily_visits": [],
        "top_pages": [],
        "top_searches": [],
        "top_downloads": [],
        "by_country": [],
        "by_device": [],
        "by_browser": [],
    }

    if not api_key or not app_id:
        empty_result["error"] = "Application Insights not configured"
        return empty_result

    window = f"{days}d"

    q_visits = f"pageViews | where timestamp > ago({window}) | summarize dcount(session_Id)"
    q_users = f"pageViews | where timestamp > ago({window}) | summarize dcount(user_Id)"
    q_pv = f"pageViews | where timestamp > ago({window}) | summarize count()"
    q_session_duration = (
        f"pageViews | where timestamp > ago({window}) "
        f"| summarize mn=min(timestamp), mx=max(timestamp) by session_Id "
        f"| extend duration_s = datetime_diff('second', mx, mn) "
        f"| summarize avg(duration_s)"
    )
    q_bounce = (
        f"pageViews | where timestamp > ago({window}) "
        f"| summarize pv=count() by session_Id "
        f"| summarize bounced = countif(pv == 1), total = count() "
        f"| extend bounce_rate = iff(total > 0, (bounced * 100.0) / total, 0.0) "
        f"| project bounce_rate"
    )
    q_daily = (
        f"pageViews | where timestamp > ago({window}) "
        f"| summarize visits=dcount(session_Id), pageviews=count() by bin(timestamp, 1d) "
        f"| order by timestamp asc"
    )
    q_top_pages = (
        f"pageViews | where timestamp > ago({window}) "
        f"| summarize views=count(), avg_load=avg(duration) by name "
        f"| top 20 by views"
    )
    q_dwell = (
        f"customEvents | where name == 'DwellTime' and timestamp > ago({window}) "
        f"| extend page = tostring(customDimensions.page), "
        f"         secs = todouble(customDimensions.seconds) "
        f"| where isnotempty(page) "
        f"| summarize avg_dwell=avg(secs) by page"
    )
    q_searches = (
        f"customEvents | where name == 'Search' and timestamp > ago({window}) "
        f"| extend q = tostring(customDimensions.query) "
        f"| where isnotempty(q) "
        f"| summarize c=count() by q "
        f"| top 20 by c"
    )
    q_downloads = (
        f"customEvents | where name == 'Download' and timestamp > ago({window}) "
        f"| extend fn = tostring(customDimensions.filename), "
        f"         ft = tostring(customDimensions.type) "
        f"| where isnotempty(fn) "
        f"| summarize c=count() by fn, ft "
        f"| top 20 by c"
    )
    q_country = (
        f"pageViews | where timestamp > ago({window}) "
        f"| summarize c=count() by client_CountryOrRegion "
        f"| top 20 by c"
    )
    q_device = (
        f"pageViews | where timestamp > ago({window}) "
        f"| summarize c=count() by client_Type "
        f"| top 10 by c"
    )
    q_browser = (
        f"pageViews | where timestamp > ago({window}) "
        f"| summarize c=count() by client_Browser "
        f"| top 10 by c"
    )

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        results = await asyncio.gather(
            _run_query(client, app_id, api_key, q_visits),
            _run_query(client, app_id, api_key, q_users),
            _run_query(client, app_id, api_key, q_pv),
            _run_query(client, app_id, api_key, q_session_duration),
            _run_query(client, app_id, api_key, q_bounce),
            _run_query(client, app_id, api_key, q_daily),
            _run_query(client, app_id, api_key, q_top_pages),
            _run_query(client, app_id, api_key, q_dwell),
            _run_query(client, app_id, api_key, q_searches),
            _run_query(client, app_id, api_key, q_downloads),
            _run_query(client, app_id, api_key, q_country),
            _run_query(client, app_id, api_key, q_device),
            _run_query(client, app_id, api_key, q_browser),
            return_exceptions=False,
        )

    (
        rows_visits, rows_users, rows_pv, rows_sd, rows_bounce,
        rows_daily, rows_pages, rows_dwell, rows_searches, rows_downloads,
        rows_country, rows_device, rows_browser,
    ) = results

    total_visits = int(_first_cell(rows_visits, 0) or 0)
    unique_visitors = int(_first_cell(rows_users, 0) or 0)
    total_pageviews = int(_first_cell(rows_pv, 0) or 0)
    avg_session_sec = round(float(_first_cell(rows_sd, 0) or 0), 1)
    bounce_rate = round(float(_first_cell(rows_bounce, 0) or 0), 1)

    daily_visits = [
        {
            "date": (row[0][:10] if isinstance(row[0], str) else str(row[0])[:10]),
            "visits": int(row[1] or 0),
            "pageviews": int(row[2] or 0),
        }
        for row in rows_daily
        if len(row) >= 3
    ]

    dwell_by_page: dict[str, float] = {
        str(row[0]): round(float(row[1] or 0), 1)
        for row in rows_dwell
        if len(row) >= 2 and row[0]
    }

    top_pages = [
        {
            "path": str(row[0] or "(unknown)"),
            "views": int(row[1] or 0),
            "avg_dwell_sec": dwell_by_page.get(str(row[0] or ""), 0),
            "avg_load_ms": round(float(row[2] or 0), 1),
        }
        for row in rows_pages
        if len(row) >= 3
    ]

    top_searches = [
        {"query": str(row[0] or ""), "count": int(row[1] or 0)}
        for row in rows_searches
        if len(row) >= 2
    ]

    top_downloads = [
        {
            "filename": str(row[0] or ""),
            "type": str(row[1] or ""),
            "count": int(row[2] or 0),
        }
        for row in rows_downloads
        if len(row) >= 3
    ]

    by_country = [
        {"country": str(row[0] or "Unknown"), "visits": int(row[1] or 0)}
        for row in rows_country
        if len(row) >= 2
    ]

    device_rows = [
        (str(row[0] or "Unknown"), int(row[1] or 0))
        for row in rows_device
        if len(row) >= 2
    ]
    device_total = sum(c for _, c in device_rows) or 1
    by_device = [
        {"device": name, "pct": round((count * 100.0) / device_total, 1)}
        for name, count in device_rows
    ]

    browser_rows = [
        (str(row[0] or "Unknown"), int(row[1] or 0))
        for row in rows_browser
        if len(row) >= 2
    ]
    browser_total = sum(c for _, c in browser_rows) or 1
    by_browser = [
        {"browser": name, "pct": round((count * 100.0) / browser_total, 1)}
        for name, count in browser_rows
    ]

    return {
        "period": f"{days}d",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_visits": total_visits,
            "unique_visitors": unique_visitors,
            "total_pageviews": total_pageviews,
            "avg_session_duration_sec": avg_session_sec,
            "bounce_rate_pct": bounce_rate,
        },
        "daily_visits": daily_visits,
        "top_pages": top_pages,
        "top_searches": top_searches,
        "top_downloads": top_downloads,
        "by_country": by_country,
        "by_device": by_device,
        "by_browser": by_browser,
    }
