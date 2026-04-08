"""Azure Functions v2 entry point — wraps FastAPI via ASGI adapter.

Includes timer triggers for:
- Weekly event discovery (Gemini AI → Azure SQL)
- Daily past event purge (48hr cutoff)
"""

import logging
import os

import azure.functions as func
from app.main import app as fastapi_app

logger = logging.getLogger(__name__)

app = func.AsgiFunctionApp(app=fastapi_app, http_auth_level=func.AuthLevel.ANONYMOUS)


@app.timer_trigger(
    schedule="0 0 10 * * 1",  # Every Monday at 10:00 UTC
    arg_name="timer",
    run_on_startup=False,
)
def discover_events_timer(timer: func.TimerRequest) -> None:
    """Weekly event discovery — Azure → Gemini → Azure SQL."""
    from app.services.event_discovery import discover_events

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    sql_conn = os.environ.get("AZURE_SQL_CONNECTION_STRING", "")

    if not gemini_key or not sql_conn:
        logger.error("Missing GEMINI_API_KEY or AZURE_SQL_CONNECTION_STRING")
        return

    logger.info("Starting weekly event discovery...")
    result = discover_events(gemini_key, sql_conn)
    logger.info("Event discovery complete: %d new, %d updated, %d errors",
                result["new"], result["updated"], len(result["errors"]))


@app.timer_trigger(
    schedule="0 0 6 * * *",  # Daily at 06:00 UTC
    arg_name="timer",
    run_on_startup=False,
)
def purge_past_events_timer(timer: func.TimerRequest) -> None:
    """Daily purge of events that ended 48+ hours ago."""
    from app.services.event_discovery import purge_past_events

    sql_conn = os.environ.get("AZURE_SQL_CONNECTION_STRING", "")
    if not sql_conn:
        logger.error("Missing AZURE_SQL_CONNECTION_STRING")
        return

    deleted = purge_past_events(sql_conn)
    logger.info("Purged %d past events", deleted)
