#!/usr/bin/env python3
"""Generate enhanced PDFs with real selectable text overlaid on scanned pages.

Takes scanned-only PDFs, extracts text via Gemini AI vision (or existing OCR),
and creates new PDFs with an invisible text layer over the original scanned images.
This makes the documents searchable, selectable, and accessible to screen readers.

Only processes PDFs with substantial readable text content (manuals, handbooks,
service instructions) — skips drawing-heavy documents with minimal text.

Usage:
    python enhance_pdfs.py                    # Process all eligible PDFs
    python enhance_pdfs.py --list             # List eligible PDFs
    python enhance_pdfs.py --manual-id X      # Process specific manual
    python enhance_pdfs.py --dry-run          # Preview without uploading

Environment variables:
    GEMINI_API_KEY
    AZURE_BLOB_CONNECTION_STRING
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF required: pip install PyMuPDF")
    sys.exit(1)

from azure.storage.blob import BlobServiceClient

# PDFs worth enhancing — ones with substantial readable text
# (not engineering drawing sheets that are mostly diagrams)
ELIGIBLE_PDFS = [
    {
        "id": "erection-maintenance",
        "container": "manuals",
        "blob": "Stearman_Erection_and_Maintenance_Instructions_PT-13D_N2S-5.pdf",
        "reason": "Full maintenance manual with procedures, tables, specs",
    },
    {
        "id": "service-instructions",
        "container": "reference-archive",
        "blob": "stearman-aero/Service_Instructions_for_Army_Models_PT-13B-17_and_-18.pdf",
        "reason": "Service instructions with detailed procedures",
    },
    {
        "id": "overhaul-handbook",
        "container": "reference-archive",
        "blob": "stearman-aero/Handbook_of_Overhaul_Instructions_for_the_Models_PT-13B_PT-17_and_PT-18_Primary_Training_Airplanes.pdf",
        "reason": "Overhaul procedures with step-by-step text",
    },
    {
        "id": "structural-repair",
        "container": "reference-archive",
        "blob": "stearman-aero/Structural_Repair_Instructions_for_Army_Model_PT-13D_and_Navy_Model_N2S-5_Airplanes.pdf",
        "reason": "Repair procedures with text content",
    },
    {
        "id": "pilot-fop",
        "container": "reference-archive",
        "blob": "stearman-aero/Pilots_Flight_Operating_Instructions_for_the_Army_Model_PT-13D_and_Navy_Model_N2S-5_Airplanes.pdf",
        "reason": "Pilot operating instructions — text-heavy",
    },
    {
        "id": "pilot-handbook-n2s1-3",
        "container": "reference-archive",
        "blob": "stearman-aero/Pilots_Handbook_for_Stearman_Airplanes_Models_N2S-1_N2S-2_and_N2S-3.pdf",
        "reason": "Pilot handbook with procedures",
    },
    {
        "id": "continental-r670",
        "container": "reference-archive",
        "blob": "stearman-aero/Continental_W-670_R-670_Overhaul_Instructions.pdf",
        "reason": "Engine overhaul — text-heavy procedures",
    },
]


def get_blob_service():
    return BlobServiceClient.from_connection_string(os.environ["AZURE_BLOB_CONNECTION_STRING"])


def extract_text_with_gemini(image_bytes: bytes, api_key: str) -> str:
    """Use Gemini to extract all readable text from a scanned page image."""
    import urllib.request
    from PIL import Image

    # Resize for API
    img = Image.open(io.BytesIO(image_bytes))
    img.thumbnail((1500, 1500))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    b64 = base64.b64encode(buf.getvalue()).decode()

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}"
    payload = json.dumps({
        "contents": [{
            "parts": [
                {"text": "Extract ALL readable text from this scanned document page. Preserve the original layout, paragraph structure, headings, numbered lists, and table formatting as closely as possible. Include every word you can read. Output only the extracted text, nothing else."},
                {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
            ]
        }]
    }).encode()

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

    for attempt in range(3):
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
            return resp["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            if attempt < 2:
                log.warning("Gemini retry %d: %s", attempt + 1, e)
                time.sleep(5 * (attempt + 1))
            else:
                log.error("Gemini failed after 3 attempts: %s", e)
                return ""
    return ""


def has_embedded_text(page) -> bool:
    """Check if a PDF page already has selectable text."""
    text = page.get_text().strip()
    return len(text) > 50


def enhance_pdf(pdf_info: dict, api_key: str, dry_run: bool = False) -> None:
    """Download a scanned PDF, add text layer via AI, upload enhanced version."""
    blob_svc = get_blob_service()
    container = blob_svc.get_container_client(pdf_info["container"])

    log.info("Processing: %s", pdf_info["blob"])

    # Download original
    blob_data = container.download_blob(pdf_info["blob"]).readall()
    log.info("  Downloaded: %.1f MB", len(blob_data) / 1048576)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(blob_data)
        tmp_path = tmp.name

    doc = fitz.open(tmp_path)
    total_pages = len(doc)
    enhanced_count = 0
    skipped_count = 0

    log.info("  Pages: %d", total_pages)

    for i in range(total_pages):
        page = doc[i]

        # Skip pages that already have embedded text
        if has_embedded_text(page):
            skipped_count += 1
            if (i + 1) % 20 == 0:
                log.info("  Page %d/%d (skipped — already has text)", i + 1, total_pages)
            continue

        if (i + 1) % 10 == 0 or i == 0:
            log.info("  Page %d/%d (extracting text via AI)", i + 1, total_pages)

        # Render page to image for Gemini
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("jpeg")

        # Extract text with Gemini
        text = extract_text_with_gemini(img_bytes, api_key)

        if text and not dry_run:
            # Insert invisible text layer over the page
            # This makes the text selectable/searchable while keeping the original scan visible
            tw = fitz.TextWriter(page.rect)
            fontsize = 10
            font = fitz.Font("helv")

            # Simple approach: insert the text as a hidden overlay
            # positioned at the top of the page, with very small transparent font
            y_pos = 20.0
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    y_pos += fontsize * 1.2
                    continue
                try:
                    tw.append((20, y_pos), line, font=font, fontsize=fontsize)
                    y_pos += fontsize * 1.2
                except Exception:
                    pass
                if y_pos > page.rect.height - 20:
                    break

            # Write with invisible ink (alpha=0) so it doesn't obscure the scan
            tw.write_text(page, opacity=0)
            enhanced_count += 1

        # Rate limit for Gemini
        time.sleep(0.3)

    if not dry_run:
        # Save enhanced PDF
        enhanced_path = tmp_path + ".enhanced.pdf"
        doc.save(enhanced_path)
        doc.close()

        # Upload to a new "enhanced" container
        enhanced_container = blob_svc.get_container_client("manuals-enhanced")
        try:
            enhanced_container.create_container()
        except Exception:
            pass

        blob_name = Path(pdf_info["blob"]).name
        with open(enhanced_path, "rb") as f:
            enhanced_container.upload_blob(blob_name, f, overwrite=True)
        enhanced_size = os.path.getsize(enhanced_path)

        log.info("  Uploaded enhanced PDF: %.1f MB (%d pages enhanced, %d skipped)",
                 enhanced_size / 1048576, enhanced_count, skipped_count)

        os.unlink(enhanced_path)
    else:
        doc.close()
        log.info("  DRY RUN: would enhance %d pages, skip %d", total_pages - skipped_count, skipped_count)

    os.unlink(tmp_path)


def main():
    parser = argparse.ArgumentParser(description="Enhance scanned PDFs with AI text layer")
    parser.add_argument("--list", action="store_true", help="List eligible PDFs")
    parser.add_argument("--manual-id", type=str, help="Process specific manual")
    parser.add_argument("--dry-run", action="store_true", help="Preview without uploading")
    args = parser.parse_args()

    if args.list:
        print("Eligible PDFs for text enhancement:")
        for pdf in ELIGIBLE_PDFS:
            print(f"  {pdf['id']:30s} — {pdf['reason']}")
        return

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not set")
        sys.exit(1)

    pdfs = ELIGIBLE_PDFS
    if args.manual_id:
        pdfs = [p for p in pdfs if p["id"] == args.manual_id]
        if not pdfs:
            print(f"Manual '{args.manual_id}' not found")
            sys.exit(1)

    for pdf in pdfs:
        enhance_pdf(pdf, api_key, dry_run=args.dry_run)

    log.info("All done!")


if __name__ == "__main__":
    main()
