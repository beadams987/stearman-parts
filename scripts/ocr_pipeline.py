#!/usr/bin/env python3
"""Batch OCR pipeline for Stearman Parts images and PDF manuals.

Processes pre-rendered JPEG images from Azure Blob Storage through Tesseract OCR,
stores extracted text in Azure SQL (Images.OcrText column), and optionally updates
the Azure AI Search index.

Usage:
    python ocr_pipeline.py                     # Process all unprocessed images
    python ocr_pipeline.py --limit 100         # Process up to 100 images
    python ocr_pipeline.py --start-from 100500 # Resume from a specific ImageID
    python ocr_pipeline.py --dry-run           # Preview without writing to DB
    python ocr_pipeline.py --pdfs-only         # Only process PDF manuals

Environment variables (same as api/app/config.py):
    AZURE_SQL_CONNECTION_STRING
    AZURE_BLOB_CONNECTION_STRING
    BLOB_RENDERS_CONTAINER_NAME (default: renders)
    BLOB_MANUALS_CONTAINER_NAME (default: manuals)
    AZURE_SEARCH_ENDPOINT (optional)
    AZURE_SEARCH_KEY (optional)
    AZURE_SEARCH_INDEX (default: stearman-index)
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pyodbc
from azure.storage.blob import BlobServiceClient
from PIL import Image

try:
    import pytesseract
except ImportError:
    print("pytesseract not installed. Run: pip install pytesseract")
    sys.exit(1)

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None
    print("WARNING: PyMuPDF not installed. PDF text extraction unavailable. pip install PyMuPDF")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

CHECKPOINT_FILE = Path(__file__).parent / "ocr_checkpoint.json"


def load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        return json.loads(CHECKPOINT_FILE.read_text())
    return {"last_image_id": 0, "processed": 0, "errors": 0}


def save_checkpoint(state: dict) -> None:
    CHECKPOINT_FILE.write_text(json.dumps(state, indent=2))


def get_db_connection() -> pyodbc.Connection:
    conn_str = os.environ["AZURE_SQL_CONNECTION_STRING"]
    return pyodbc.connect(conn_str, autocommit=False)


def get_blob_service(container: str) -> tuple:
    conn_str = os.environ["AZURE_BLOB_CONNECTION_STRING"]
    svc = BlobServiceClient.from_connection_string(conn_str)
    return svc, svc.get_container_client(container)


def ocr_image_blob(container_client, blob_path: str) -> str:
    """Download a rendered JPEG from blob storage and run Tesseract OCR."""
    try:
        blob_data = container_client.download_blob(blob_path).readall()
    except Exception as e:
        log.warning("Failed to download blob %s: %s", blob_path, e)
        return ""

    img = Image.open(io.BytesIO(blob_data))
    text = pytesseract.image_to_string(img, lang="eng", config="--psm 6")
    return text.strip()


def extract_pdf_text(container_client, blob_name: str) -> list[dict]:
    """Extract text from a PDF in blob storage. Returns list of {page, text}."""
    if fitz is None:
        log.warning("PyMuPDF not available, skipping PDF %s", blob_name)
        return []

    blob_data = container_client.download_blob(blob_name).readall()

    pages = []
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(blob_data)
        tmp_path = tmp.name

    try:
        doc = fitz.open(tmp_path)
        for i, page in enumerate(doc):
            text = page.get_text().strip()
            # If no embedded text, try OCR via Tesseract on rendered page image
            if len(text) < 20:
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                text = pytesseract.image_to_string(img, lang="eng", config="--psm 6").strip()
            pages.append({"page": i + 1, "text": text})
        doc.close()
    finally:
        os.unlink(tmp_path)

    return pages


def process_images(args: argparse.Namespace) -> None:
    """Process rendered JPEG images through OCR and store text in SQL."""
    conn = get_db_connection()
    cursor = conn.cursor()

    renders_container = os.environ.get("BLOB_RENDERS_CONTAINER_NAME", "renders")
    _, container_client = get_blob_service(renders_container)

    checkpoint = load_checkpoint()
    start_from = args.start_from or checkpoint.get("last_image_id", 0)

    # Fetch images that need OCR
    cursor.execute(
        """
        SELECT ImageID, RenderPath
        FROM Images
        WHERE (OcrText IS NULL OR OcrText = '')
          AND RenderPath IS NOT NULL
          AND ImageID > ?
        ORDER BY ImageID
        """,
        start_from,
    )

    rows = cursor.fetchall()
    total = len(rows)
    if args.limit:
        rows = rows[: args.limit]

    log.info("Found %d images needing OCR (processing %d)", total, len(rows))

    processed = checkpoint.get("processed", 0)
    errors = checkpoint.get("errors", 0)

    for i, row in enumerate(rows):
        image_id = row.ImageID
        render_path = row.RenderPath

        if (i + 1) % 100 == 0 or i == 0:
            log.info("Processing %d/%d (ImageID=%d)", i + 1, len(rows), image_id)

        try:
            text = ocr_image_blob(container_client, render_path)

            if not args.dry_run and text:
                cursor.execute(
                    "UPDATE Images SET OcrText = ?, ModifiedAt = ? WHERE ImageID = ?",
                    text,
                    datetime.now(UTC),
                    image_id,
                )
                conn.commit()

            processed += 1
        except Exception as e:
            log.error("Error processing ImageID=%d: %s", image_id, e)
            errors += 1
            conn.rollback()

        # Save checkpoint every 50 images
        if (i + 1) % 50 == 0:
            save_checkpoint({
                "last_image_id": image_id,
                "processed": processed,
                "errors": errors,
            })

    save_checkpoint({
        "last_image_id": rows[-1].ImageID if rows else start_from,
        "processed": processed,
        "errors": errors,
        "completed_at": datetime.now(UTC).isoformat(),
    })

    log.info("Done! Processed=%d, Errors=%d", processed, errors)
    conn.close()


def process_pdfs(args: argparse.Namespace) -> None:
    """Extract text from PDF manuals and store in ManualPages table."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create ManualPages table if it doesn't exist
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='ManualPages' AND xtype='U')
        CREATE TABLE ManualPages (
            PageID INT IDENTITY PRIMARY KEY,
            ManualID NVARCHAR(100) NOT NULL,
            PageNumber INT NOT NULL,
            PageText NVARCHAR(MAX),
            CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
            UNIQUE (ManualID, PageNumber)
        )
    """)
    conn.commit()

    manuals_container = os.environ.get("BLOB_MANUALS_CONTAINER_NAME", "manuals")
    _, container_client = get_blob_service(manuals_container)

    # List all PDFs in the manuals container
    blobs = list(container_client.list_blobs())
    pdfs = [b for b in blobs if b.name.lower().endswith(".pdf")]
    log.info("Found %d PDF manuals to process", len(pdfs))

    for blob in pdfs:
        # Derive a manual_id from filename
        manual_id = blob.name.rsplit(".", 1)[0].replace(" ", "_")
        log.info("Processing PDF: %s (manual_id=%s)", blob.name, manual_id)

        # Check if already processed
        cursor.execute(
            "SELECT COUNT(*) FROM ManualPages WHERE ManualID = ?", manual_id
        )
        existing = cursor.fetchone()[0]
        if existing > 0 and not args.dry_run:
            log.info("  Already has %d pages indexed, skipping", existing)
            continue

        pages = extract_pdf_text(container_client, blob.name)
        log.info("  Extracted text from %d pages", len(pages))

        if not args.dry_run:
            for page in pages:
                if page["text"]:
                    cursor.execute(
                        """
                        MERGE ManualPages AS target
                        USING (SELECT ? AS ManualID, ? AS PageNumber) AS source
                        ON target.ManualID = source.ManualID AND target.PageNumber = source.PageNumber
                        WHEN MATCHED THEN UPDATE SET PageText = ?, CreatedAt = GETUTCDATE()
                        WHEN NOT MATCHED THEN INSERT (ManualID, PageNumber, PageText) VALUES (?, ?, ?);
                        """,
                        manual_id,
                        page["page"],
                        page["text"],
                        manual_id,
                        page["page"],
                        page["text"],
                    )
            conn.commit()
            log.info("  Saved %d pages to ManualPages", len(pages))

    conn.close()
    log.info("PDF processing complete!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stearman Parts OCR Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Preview without DB writes")
    parser.add_argument("--limit", type=int, help="Max images to process")
    parser.add_argument("--start-from", type=int, help="Start from this ImageID")
    parser.add_argument("--pdfs-only", action="store_true", help="Only process PDF manuals")
    parser.add_argument("--images-only", action="store_true", help="Only process images (skip PDFs)")
    args = parser.parse_args()

    if not args.pdfs_only:
        log.info("=== Phase 1: Image OCR ===")
        process_images(args)

    if not args.images_only:
        log.info("=== Phase 2: PDF Text Extraction ===")
        process_pdfs(args)


if __name__ == "__main__":
    main()
