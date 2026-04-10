#!/usr/bin/env python3
"""OCR pipeline for PDF manuals.

Extracts text from PDF manuals stored in Azure Blob Storage.
Uses PyMuPDF (fitz) for text-searchable PDFs, falls back to Tesseract
for scanned pages. Stores extracted text per page in the ManualPages table.

Usage:
    python ocr_pdfs.py
    python ocr_pdfs.py --dry-run
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import sys
import tempfile
from typing import Any

import fitz  # PyMuPDF
import pyodbc
from azure.storage.blob import BlobServiceClient
from PIL import Image

try:
    import pytesseract
except ImportError:
    pytesseract = None  # type: ignore[assignment]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment configuration (matches api/app/config.py)
# ---------------------------------------------------------------------------

AZURE_SQL_CONNECTION_STRING = os.environ.get("AZURE_SQL_CONNECTION_STRING", "")
AZURE_BLOB_CONNECTION_STRING = os.environ.get("AZURE_BLOB_CONNECTION_STRING", "")
BLOB_MANUALS_CONTAINER_NAME = os.environ.get("BLOB_MANUALS_CONTAINER_NAME", "manuals")

# Known manuals (matches api/app/routers/manuals.py)
MANUALS = [
    {
        "id": "erection-maintenance",
        "title": "Erection & Maintenance Instructions",
        "filename": "Stearman_Erection_and_Maintenance_Instructions_PT-13D_N2S-5.pdf",
    },
    {
        "id": "parts-catalog",
        "title": "Parts Catalog",
        "filename": "Stearman_Parts_Catalog_PT-13D_N2S-5.pdf",
    },
]


def ensure_manual_pages_table(conn: pyodbc.Connection) -> None:
    """Create the ManualPages table if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute("""
        IF NOT EXISTS (
            SELECT * FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'ManualPages'
        )
        BEGIN
            CREATE TABLE ManualPages (
                ManualPageID INT IDENTITY(1,1) PRIMARY KEY,
                ManualID NVARCHAR(100) NOT NULL,
                PageNumber INT NOT NULL,
                PageText NVARCHAR(MAX),
                CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
                INDEX IX_ManualPages_Manual NONCLUSTERED (ManualID, PageNumber)
            )
        END
    """)
    conn.commit()
    logger.info("ManualPages table ready")


def get_processed_pages(conn: pyodbc.Connection, manual_id: str) -> set[int]:
    """Return set of page numbers already processed for a manual."""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT PageNumber FROM ManualPages WHERE ManualID = ?",
            manual_id,
        )
        return {row.PageNumber for row in cursor.fetchall()}
    except Exception:
        return set()


def download_pdf(blob_service: BlobServiceClient, filename: str) -> bytes | None:
    """Download a PDF manual from Azure Blob Storage."""
    container = blob_service.get_container_client(BLOB_MANUALS_CONTAINER_NAME)
    try:
        blob_client = container.get_blob_client(filename)
        return blob_client.download_blob().readall()
    except Exception:
        logger.exception("Failed to download %s", filename)
        return None


def extract_text_from_page(page: fitz.Page) -> str:
    """Extract text from a PDF page. Use embedded text first, fall back to OCR."""
    # Try embedded text first (many PDFs are already text-searchable)
    text = page.get_text().strip()
    if len(text) > 50:
        return text

    # Fall back to Tesseract OCR for scanned pages
    if pytesseract is None:
        logger.warning("pytesseract not available for OCR fallback")
        return text

    # Render page to image at 300 DPI
    mat = fitz.Matrix(300 / 72, 300 / 72)
    pix = page.get_pixmap(matrix=mat)
    img_data = pix.tobytes("png")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(img_data)
        tmp_path = tmp.name

    try:
        img = Image.open(tmp_path)
        ocr_text: str = pytesseract.image_to_string(img, lang="eng")
        return ocr_text.strip()
    finally:
        os.unlink(tmp_path)


def insert_page_text(
    conn: pyodbc.Connection, manual_id: str, page_number: int, text: str
) -> None:
    """Insert extracted text for a manual page."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO ManualPages (ManualID, PageNumber, PageText)
        VALUES (?, ?, ?)
        """,
        manual_id,
        page_number,
        text,
    )
    conn.commit()


def process_manual(
    conn: pyodbc.Connection,
    blob_service: BlobServiceClient,
    manual: dict[str, str],
    *,
    dry_run: bool = False,
) -> None:
    """Process a single PDF manual."""
    manual_id = manual["id"]
    filename = manual["filename"]

    logger.info("Processing manual: %s (%s)", manual["title"], filename)

    pdf_data = download_pdf(blob_service, filename)
    if pdf_data is None:
        logger.error("Could not download %s; skipping", filename)
        return

    doc = fitz.open(stream=io.BytesIO(pdf_data), filetype="pdf")
    total_pages = len(doc)
    logger.info("  %d pages in %s", total_pages, filename)

    processed_pages = get_processed_pages(conn, manual_id) if not dry_run else set()
    new_count = 0

    for page_num in range(total_pages):
        page_number = page_num + 1  # 1-based

        if page_number in processed_pages:
            continue

        if dry_run:
            if page_num < 3:
                page = doc[page_num]
                text = extract_text_from_page(page)
                logger.info("  Page %d: %d chars extracted", page_number, len(text))
            continue

        page = doc[page_num]
        text = extract_text_from_page(page)
        insert_page_text(conn, manual_id, page_number, text)
        new_count += 1

        if new_count % 50 == 0:
            logger.info("  Progress: %d / %d pages", new_count, total_pages)

    doc.close()

    if dry_run:
        logger.info("  Dry run — would process %d new pages", total_pages - len(processed_pages))
    else:
        logger.info("  Done: %d new pages inserted", new_count)


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR pipeline for PDF manuals")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    args = parser.parse_args()

    if not AZURE_SQL_CONNECTION_STRING:
        logger.error("AZURE_SQL_CONNECTION_STRING not set")
        sys.exit(1)
    if not AZURE_BLOB_CONNECTION_STRING:
        logger.error("AZURE_BLOB_CONNECTION_STRING not set")
        sys.exit(1)

    conn = pyodbc.connect(AZURE_SQL_CONNECTION_STRING)
    blob_service = BlobServiceClient.from_connection_string(AZURE_BLOB_CONNECTION_STRING)

    if not args.dry_run:
        ensure_manual_pages_table(conn)

    for manual in MANUALS:
        process_manual(conn, blob_service, manual, dry_run=args.dry_run)

    conn.close()
    logger.info("All manuals processed")


if __name__ == "__main__":
    main()
