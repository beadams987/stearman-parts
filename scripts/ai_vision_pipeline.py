#!/usr/bin/env python3
"""AI Vision pipeline for Stearman Parts — Gemini Flash-Lite image analysis.

Processes rendered JPEG images through Gemini's vision model to generate
rich contextual descriptions beyond what OCR can extract. Also processes
film transcripts for search indexing.

Stores results in:
- Images.AiDescription — rich contextual description
- Images.OcrText — raw text extraction (Tesseract fallback)
- FilmTranscripts table — searchable film/video content

Usage:
    python ai_vision_pipeline.py                    # Process all unprocessed images
    python ai_vision_pipeline.py --limit 100        # Process up to 100 images
    python ai_vision_pipeline.py --start-from 100500 # Resume from ImageID
    python ai_vision_pipeline.py --transcripts-only  # Only index film transcripts
    python ai_vision_pipeline.py --dry-run           # Preview without DB writes

Environment variables:
    GEMINI_API_KEY
    AZURE_SQL_CONNECTION_STRING
    AZURE_BLOB_CONNECTION_STRING
    BLOB_RENDERS_CONTAINER_NAME (default: renders)
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pyodbc
from azure.storage.blob import BlobServiceClient
from PIL import Image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

CHECKPOINT_FILE = Path(__file__).parent / "ai_vision_checkpoint.json"

VISION_PROMPT = """Analyze this Boeing-Stearman biplane engineering drawing. Provide:

1. **Description**: What this drawing shows (parts, assemblies, systems)
2. **Drawing Numbers**: Any drawing/part numbers visible (e.g., 73-1000)
3. **Title Block**: Company name, dates, approval signatures, sheet info
4. **Text Content**: All readable text including notes, dimensions, callouts
5. **Keywords**: 5-10 descriptive keywords for search

Format as structured text, not markdown. Be thorough but concise."""

# Rate limiting — Tier 1 paid allows 300 RPM for flash-lite
# We use 200 RPM to leave headroom and be a good citizen
REQUESTS_PER_MINUTE = 200
REQUEST_INTERVAL = 60.0 / REQUESTS_PER_MINUTE  # ~0.3s between requests


def load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        return json.loads(CHECKPOINT_FILE.read_text())
    return {"last_image_id": 0, "processed": 0, "errors": 0, "skipped": 0}


def save_checkpoint(state: dict) -> None:
    CHECKPOINT_FILE.write_text(json.dumps(state, indent=2))


def get_db() -> pyodbc.Connection:
    return pyodbc.connect(os.environ["AZURE_SQL_CONNECTION_STRING"], autocommit=False)


def get_blob_container(container: str):
    svc = BlobServiceClient.from_connection_string(os.environ["AZURE_BLOB_CONNECTION_STRING"])
    return svc.get_container_client(container)


def ensure_columns(conn: pyodbc.Connection) -> None:
    """Add AiDescription column to Images if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'Images' AND COLUMN_NAME = 'AiDescription'
        )
        ALTER TABLE Images ADD AiDescription NVARCHAR(MAX) NULL
    """)
    conn.commit()
    log.info("Ensured AiDescription column exists")


def ensure_transcripts_table(conn: pyodbc.Connection) -> None:
    """Create FilmTranscripts table if needed."""
    cursor = conn.cursor()
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='FilmTranscripts' AND xtype='U')
        CREATE TABLE FilmTranscripts (
            TranscriptID INT IDENTITY PRIMARY KEY,
            FilmName NVARCHAR(500) NOT NULL,
            BlobPath NVARCHAR(500) NOT NULL,
            TranscriptText NVARCHAR(MAX),
            Duration NVARCHAR(20),
            Source NVARCHAR(200) DEFAULT 'Whisper STT',
            CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
            UNIQUE (BlobPath)
        )
    """)
    conn.commit()


def call_gemini_vision(image_data: bytes, api_key: str) -> str:
    """Send image to Gemini Flash-Lite for analysis."""
    import urllib.request

    # Resize to save tokens/bandwidth (1200px max dimension)
    img = Image.open(io.BytesIO(image_data))
    img.thumbnail((1200, 1200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)
    b64 = base64.b64encode(buf.getvalue()).decode()

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}"
    payload = json.dumps({
        "contents": [{
            "parts": [
                {"text": VISION_PROMPT},
                {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
            ]
        }]
    }).encode()

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

    for attempt in range(3):
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
            text = resp["candidates"][0]["content"]["parts"][0]["text"]
            return text.strip()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 30 * (attempt + 1)
                log.warning("Rate limited, waiting %ds...", wait)
                time.sleep(wait)
            elif e.code == 503:
                log.warning("Service unavailable, waiting 10s...")
                time.sleep(10)
            else:
                error_body = e.read().decode()[:200]
                log.error("Gemini API error %d: %s", e.code, error_body)
                raise
        except Exception as e:
            if attempt < 2:
                log.warning("Attempt %d failed: %s, retrying...", attempt + 1, e)
                time.sleep(5)
            else:
                raise

    return ""


def process_images(args: argparse.Namespace) -> None:
    """Process rendered images through Gemini vision."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log.error("GEMINI_API_KEY not set")
        sys.exit(1)

    conn = get_db()
    ensure_columns(conn)
    cursor = conn.cursor()

    renders_container = os.environ.get("BLOB_RENDERS_CONTAINER_NAME", "renders")
    container = get_blob_container(renders_container)

    checkpoint = load_checkpoint()
    start_from = args.start_from or checkpoint.get("last_image_id", 0)

    # Fetch images needing AI analysis
    cursor.execute("""
        SELECT ImageID, RenderPath, OcrText
        FROM Images
        WHERE (AiDescription IS NULL OR AiDescription = '')
          AND RenderPath IS NOT NULL
          AND ImageID > ?
        ORDER BY ImageID
    """, start_from)

    rows = cursor.fetchall()
    total = len(rows)
    if args.limit:
        rows = rows[:args.limit]

    log.info("Found %d images needing AI vision (processing %d)", total, len(rows))

    processed = checkpoint.get("processed", 0)
    errors = checkpoint.get("errors", 0)
    skipped = checkpoint.get("skipped", 0)
    last_request_time = 0.0

    for i, row in enumerate(rows):
        image_id = row.ImageID
        render_path = row.RenderPath

        if (i + 1) % 10 == 0 or i == 0:
            log.info("Processing %d/%d (ImageID=%d) [%d ok, %d err, %d skip]",
                     i + 1, len(rows), image_id, processed, errors, skipped)

        # Rate limiting
        elapsed = time.time() - last_request_time
        if elapsed < REQUEST_INTERVAL:
            time.sleep(REQUEST_INTERVAL - elapsed)

        try:
            # Download render
            blob_data = container.download_blob(render_path).readall()
            if len(blob_data) < 1000:
                log.warning("Image %d too small (%d bytes), skipping", image_id, len(blob_data))
                skipped += 1
                continue

            # Call Gemini
            last_request_time = time.time()
            description = call_gemini_vision(blob_data, api_key)

            if not args.dry_run and description:
                cursor.execute(
                    """UPDATE Images
                       SET AiDescription = ?, ModifiedAt = ?
                       WHERE ImageID = ?""",
                    description,
                    datetime.now(UTC),
                    image_id,
                )
                conn.commit()

            if args.dry_run:
                log.info("DRY RUN — ImageID=%d description: %s", image_id, description[:150])

            processed += 1

        except Exception as e:
            log.error("Error on ImageID=%d: %s", image_id, e)
            errors += 1
            try:
                conn.rollback()
            except Exception:
                pass

        # Save checkpoint every 25 images
        if (i + 1) % 25 == 0:
            save_checkpoint({
                "last_image_id": image_id,
                "processed": processed,
                "errors": errors,
                "skipped": skipped,
                "updated_at": datetime.now(UTC).isoformat(),
            })

    # Final checkpoint
    save_checkpoint({
        "last_image_id": rows[-1].ImageID if rows else start_from,
        "processed": processed,
        "errors": errors,
        "skipped": skipped,
        "completed_at": datetime.now(UTC).isoformat(),
    })

    log.info("Image processing complete: %d processed, %d errors, %d skipped", processed, errors, skipped)
    conn.close()


def process_transcripts(args: argparse.Namespace) -> None:
    """Index Whisper film transcripts into the database."""
    conn = get_db()
    ensure_transcripts_table(conn)
    cursor = conn.cursor()

    container = get_blob_container("reference-archive")

    # List all transcript files
    blobs = list(container.list_blobs(name_starts_with="transcripts/"))
    txt_blobs = [b for b in blobs if b.name.endswith(".txt")]
    log.info("Found %d transcript files", len(txt_blobs))

    for blob in txt_blobs:
        # Derive film name from filename
        filename = blob.name.split("/")[-1]
        film_name = filename.replace(".txt", "").replace("-", " ").replace("_", " ")
        # Capitalize words
        film_name = " ".join(w.capitalize() for w in film_name.split())

        # Check if already indexed
        cursor.execute("SELECT COUNT(*) FROM FilmTranscripts WHERE BlobPath = ?", blob.name)
        if cursor.fetchone()[0] > 0:
            log.info("  Already indexed: %s", film_name)
            continue

        # Download transcript
        text = container.download_blob(blob.name).readall().decode("utf-8", errors="replace")
        log.info("  Indexing: %s (%d chars)", film_name, len(text))

        if not args.dry_run:
            cursor.execute(
                """INSERT INTO FilmTranscripts (FilmName, BlobPath, TranscriptText)
                   VALUES (?, ?, ?)""",
                film_name, blob.name, text,
            )
            conn.commit()

    log.info("Transcript indexing complete!")
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Stearman AI Vision Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Preview without DB writes")
    parser.add_argument("--limit", type=int, help="Max images to process")
    parser.add_argument("--start-from", type=int, help="Start from this ImageID")
    parser.add_argument("--transcripts-only", action="store_true", help="Only index film transcripts")
    parser.add_argument("--images-only", action="store_true", help="Only process images")
    args = parser.parse_args()

    if not args.images_only:
        log.info("=== Phase 1: Film Transcripts ===")
        process_transcripts(args)

    if not args.transcripts_only:
        log.info("=== Phase 2: AI Vision Analysis ===")
        process_images(args)


if __name__ == "__main__":
    main()
