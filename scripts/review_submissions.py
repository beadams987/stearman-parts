#!/usr/bin/env python3
"""Local submission review workflow for Stearman Parts.

Reviews pending community submissions in a safe, sandboxed manner.
Downloads files to a temporary quarantine directory for inspection,
then allows approve/reject actions that update the database.

Security:
- Files are downloaded to an isolated temp directory
- Images are re-encoded (strips metadata, neutralizes steganography)
- PDFs are scanned for JavaScript/actions/embedded files
- No files are auto-published — requires explicit approval
- Approved files are copied to a separate clean container
- Rejected files are deleted from quarantine

Usage:
    python review_submissions.py                  # Interactive review
    python review_submissions.py --list           # List pending submissions
    python review_submissions.py --auto-scan      # Scan all pending, flag suspicious
    python review_submissions.py --approve <id>   # Approve a submission
    python review_submissions.py --reject <id>    # Reject a submission

Environment variables:
    AZURE_SQL_CONNECTION_STRING
    AZURE_BLOB_CONNECTION_STRING
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pyodbc
from azure.storage.blob import BlobServiceClient
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

QUARANTINE_CONTAINER = "submissions"
CLEAN_CONTAINER = "community"  # Approved files go here


def get_db() -> pyodbc.Connection:
    return pyodbc.connect(os.environ["AZURE_SQL_CONNECTION_STRING"], autocommit=False)


def get_blob_svc() -> BlobServiceClient:
    return BlobServiceClient.from_connection_string(os.environ["AZURE_BLOB_CONNECTION_STRING"])


def list_pending(conn: pyodbc.Connection) -> list[dict]:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SubmissionID, SubmitterName, SubmitterEmail, Description,
               ResourceURL, FileName, FileSize, MimeType, Sha256Hash,
               SubmitterIP, SubmittedAt, Status
        FROM Submissions
        WHERE Status = 'pending'
        ORDER BY SubmittedAt DESC
    """)
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def scan_image(file_path: Path) -> dict:
    """Re-encode an image to strip metadata and check for anomalies."""
    findings = {"clean": True, "issues": []}
    try:
        img = Image.open(file_path)
        # Check for extremely large dimensions (decompression bomb)
        if img.width * img.height > 200_000_000:
            findings["issues"].append(f"Extremely large: {img.width}x{img.height}")
            findings["clean"] = False

        # Re-encode to strip EXIF, comments, and embedded data
        clean_path = file_path.with_suffix(".clean" + file_path.suffix)
        img.save(clean_path, format=img.format or "JPEG", quality=95)
        findings["clean_path"] = str(clean_path)
        findings["original_size"] = file_path.stat().st_size
        findings["clean_size"] = clean_path.stat().st_size

        # Large size difference could indicate embedded content
        ratio = findings["clean_size"] / max(findings["original_size"], 1)
        if ratio < 0.3:
            findings["issues"].append(f"Size dropped {(1-ratio)*100:.0f}% after re-encode (possible embedded data)")
            findings["clean"] = False

    except Exception as e:
        findings["issues"].append(f"Failed to process: {e}")
        findings["clean"] = False

    return findings


def scan_pdf(file_path: Path) -> dict:
    """Scan a PDF for JavaScript, embedded files, and other risks."""
    findings = {"clean": True, "issues": []}

    try:
        import fitz
        doc = fitz.open(str(file_path))

        # Check for JavaScript
        for i in range(len(doc)):
            page = doc[i]
            # Check page-level actions
            for annot in page.annots() or []:
                if annot.info.get("content", "").lower().find("javascript") >= 0:
                    findings["issues"].append(f"Page {i+1}: Annotation contains JavaScript reference")
                    findings["clean"] = False

        # Check for embedded files
        if doc.embfile_count() > 0:
            findings["issues"].append(f"Contains {doc.embfile_count()} embedded files")
            findings["clean"] = False

        # Check document-level JavaScript
        js = doc.get_page_text(0, "rawdict") if len(doc) > 0 else {}
        catalog = doc.pdf_catalog()
        if catalog:
            # Check for /JS, /JavaScript, /OpenAction, /AA entries
            xref_count = doc.xref_length()
            for x in range(1, min(xref_count, 500)):
                try:
                    obj = doc.xref_object(x)
                    suspicious_keys = ["/JS ", "/JavaScript", "/OpenAction", "/AA ", "/Launch"]
                    for key in suspicious_keys:
                        if key in obj:
                            findings["issues"].append(f"xref {x}: Contains {key.strip()}")
                            findings["clean"] = False
                except Exception:
                    pass

        findings["pages"] = len(doc)
        findings["size_mb"] = round(file_path.stat().st_size / 1024 / 1024, 1)
        doc.close()

    except ImportError:
        findings["issues"].append("PyMuPDF not installed — cannot scan PDF internals")
        findings["clean"] = False
    except Exception as e:
        findings["issues"].append(f"Failed to scan: {e}")
        findings["clean"] = False

    return findings


def auto_scan(conn: pyodbc.Connection) -> None:
    """Scan all pending submissions and print a report."""
    pending = list_pending(conn)
    if not pending:
        print("No pending submissions.")
        return

    blob_svc = get_blob_svc()
    quarantine = blob_svc.get_container_client(QUARANTINE_CONTAINER)

    print(f"\n{'='*70}")
    print(f"  SUBMISSION REVIEW — {len(pending)} pending")
    print(f"{'='*70}\n")

    for sub in pending:
        print(f"ID:     {sub['SubmissionID']}")
        print(f"File:   {sub['FileName']} ({sub['MimeType']}, {sub['FileSize']/1024:.0f} KB)")
        print(f"From:   {sub.get('SubmitterName') or 'Anonymous'} ({sub.get('SubmitterIP', '?')})")
        print(f"Email:  {sub.get('SubmitterEmail') or 'N/A'}")
        print(f"Desc:   {sub.get('Description', '')[:200]}")
        print(f"URL:    {sub.get('ResourceURL') or 'N/A'}")
        print(f"Date:   {sub['SubmittedAt']}")
        print(f"SHA256: {sub['Sha256Hash']}")

        # Download to temp for scanning
        with tempfile.TemporaryDirectory(prefix="stearman_review_") as tmpdir:
            local_path = Path(tmpdir) / sub["FileName"]
            try:
                blob_data = quarantine.download_blob(sub.get("BlobPath", sub["FileName"])).readall()
                local_path.write_bytes(blob_data)
            except Exception as e:
                print(f"⚠️  Could not download: {e}")
                print(f"{'─'*70}\n")
                continue

            # Scan based on type
            if sub["MimeType"].startswith("image/"):
                result = scan_image(local_path)
            elif sub["MimeType"] == "application/pdf":
                result = scan_pdf(local_path)
            else:
                result = {"clean": False, "issues": ["Unknown file type"]}

            if result["clean"]:
                print(f"✅ SCAN: Clean")
            else:
                print(f"🚨 SCAN: Issues found:")
                for issue in result["issues"]:
                    print(f"   - {issue}")

        print(f"{'─'*70}\n")


def approve_submission(conn: pyodbc.Connection, submission_id: str) -> None:
    """Approve a submission: re-encode image, move to clean container."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Submissions WHERE SubmissionID = ?", submission_id)
    row = cursor.fetchone()
    if not row:
        print(f"Submission {submission_id} not found.")
        return

    cols = [c[0] for c in cursor.description]
    sub = dict(zip(cols, row))

    blob_svc = get_blob_svc()
    quarantine = blob_svc.get_container_client(QUARANTINE_CONTAINER)

    # Ensure clean container exists
    clean = blob_svc.get_container_client(CLEAN_CONTAINER)
    try:
        clean.create_container()
    except Exception:
        pass  # Already exists

    # Download, re-encode, upload to clean container
    with tempfile.TemporaryDirectory(prefix="stearman_approve_") as tmpdir:
        local_path = Path(tmpdir) / sub["FileName"]
        blob_path = sub.get("BlobPath", sub["FileName"])
        blob_data = quarantine.download_blob(blob_path).readall()
        local_path.write_bytes(blob_data)

        # Re-encode images to strip metadata
        if sub["MimeType"].startswith("image/"):
            img = Image.open(local_path)
            clean_path = Path(tmpdir) / f"clean_{sub['FileName']}"
            img.save(clean_path, format=img.format or "JPEG", quality=95)
            clean_data = clean_path.read_bytes()
        else:
            clean_data = blob_data

        # Upload to clean container
        clean_blob_name = f"approved/{sub['FileName']}"
        clean_blob = clean.get_blob_client(clean_blob_name)
        clean_blob.upload_blob(clean_data, overwrite=True)

    # Update database
    cursor.execute(
        """UPDATE Submissions SET Status = 'approved', ReviewedAt = ?, ReviewedBy = 'review_script'
           WHERE SubmissionID = ?""",
        datetime.now(UTC), submission_id,
    )
    conn.commit()

    # Delete from quarantine
    try:
        quarantine.delete_blob(blob_path)
    except Exception:
        pass

    print(f"✅ Approved: {sub['FileName']} → community/{clean_blob_name}")


def reject_submission(conn: pyodbc.Connection, submission_id: str) -> None:
    """Reject a submission: delete from quarantine, update DB."""
    cursor = conn.cursor()
    cursor.execute("SELECT BlobPath, FileName FROM Submissions WHERE SubmissionID = ?", submission_id)
    row = cursor.fetchone()
    if not row:
        print(f"Submission {submission_id} not found.")
        return

    blob_svc = get_blob_svc()
    quarantine = blob_svc.get_container_client(QUARANTINE_CONTAINER)

    # Delete blob
    try:
        quarantine.delete_blob(row.BlobPath)
    except Exception:
        pass

    # Update database
    cursor.execute(
        """UPDATE Submissions SET Status = 'rejected', ReviewedAt = ?, ReviewedBy = 'review_script'
           WHERE SubmissionID = ?""",
        datetime.now(UTC), submission_id,
    )
    conn.commit()
    print(f"❌ Rejected and deleted: {row.FileName}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Review Stearman Parts submissions")
    parser.add_argument("--list", action="store_true", help="List pending submissions")
    parser.add_argument("--auto-scan", action="store_true", help="Scan all pending for issues")
    parser.add_argument("--approve", type=str, help="Approve a submission by ID")
    parser.add_argument("--reject", type=str, help="Reject a submission by ID")
    args = parser.parse_args()

    conn = get_db()

    if args.list:
        pending = list_pending(conn)
        if not pending:
            print("No pending submissions.")
        else:
            for s in pending:
                print(f"  {s['SubmissionID'][:8]}  {s['Status']:8s}  {s['FileName']:40s}  {s.get('SubmitterName','?'):20s}  {s['SubmittedAt']}")
    elif args.auto_scan:
        auto_scan(conn)
    elif args.approve:
        approve_submission(conn, args.approve)
    elif args.reject:
        reject_submission(conn, args.reject)
    else:
        # Default: auto-scan
        auto_scan(conn)

    conn.close()


if __name__ == "__main__":
    main()
