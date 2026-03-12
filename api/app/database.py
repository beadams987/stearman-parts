"""Database connection management for Azure SQL."""

from collections.abc import Generator
from contextlib import contextmanager

import pyodbc

from app.config import get_settings


@contextmanager
def get_db_connection() -> Generator[pyodbc.Connection, None, None]:
    """Yield a pyodbc connection to Azure SQL, closing it when done.

    Usage::

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ...")
    """
    settings = get_settings()
    conn = pyodbc.connect(settings.AZURE_SQL_CONNECTION_STRING)
    try:
        yield conn
    finally:
        conn.close()


def get_db() -> Generator[pyodbc.Connection, None, None]:
    """FastAPI dependency that provides a database connection."""
    with get_db_connection() as conn:
        yield conn
