"""Community resource submission endpoint with security hardening.

Uploads go to a quarantine blob container that is:
- NOT publicly accessible
- NOT served by the frontend (no CDN, no SAS URLs to users)
- Has no execute permissions
- Scanned by a local review script before anything is published

Security controls:
1. hCaptcha verification (anti-bot)
2. File-type allowlist (images + PDFs only, validated by magic bytes)
3. Silent discard of executables/scripts (attacker sees success)
4. File size limit (default 50 MB)
5. Rate limiting via IP (10 submissions per hour per IP)
6. Filename sanitization (no path traversal)
7. Metadata stored in SQL for audit trail
8. Quarantine storage: no public access, no SAS generation from app
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Annotated

import httpx
import pyodbc
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.database import get_db
from app.services.blob_service import BlobService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/submissions", tags=["submissions"])

# ── Constants ─────────────────────────────────────────────────────────

# Allowed MIME types and their magic bytes
ALLOWED_TYPES: dict[str, list[bytes]] = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/tiff": [b"II\x2a\x00", b"MM\x00\x2a"],  # Little-endian and big-endian TIFF
    "image/gif": [b"GIF87a", b"GIF89a"],
    "image/webp": [b"RIFF"],  # RIFF....WEBP
    "application/pdf": [b"%PDF"],
}

# Extensions that indicate executable/script content — SILENTLY DISCARD
DANGEROUS_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".com", ".msi", ".scr", ".pif", ".vbs", ".vbe",
    ".js", ".jse", ".ws", ".wsf", ".wsc", ".wsh", ".ps1", ".psm1", ".psd1",
    ".sh", ".bash", ".csh", ".ksh", ".py", ".pyw", ".rb", ".pl", ".php",
    ".asp", ".aspx", ".jsp", ".dll", ".so", ".dylib", ".elf", ".bin",
    ".app", ".action", ".command", ".workflow", ".reg", ".inf", ".lnk",
    ".html", ".htm", ".svg", ".xml", ".xsl", ".xslt",  # Can contain scripts
    ".jar", ".class", ".war", ".ear",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",  # Could contain executables
}

# Dangerous magic bytes — executables disguised with safe extensions
DANGEROUS_MAGIC: list[bytes] = [
    b"MZ",           # PE executables (.exe, .dll)
    b"\x7fELF",      # ELF binaries (Linux)
    b"\xfe\xed\xfa", # Mach-O (macOS)
    b"\xca\xfe\xba", # Mach-O fat binary
    b"PK\x03\x04",   # ZIP archive (could be .jar, .docm with macros)
    b"Rar!\x1a\x07", # RAR archive
]

# Rate limiting: IP -> list of timestamps
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_MAX = 10
RATE_LIMIT_WINDOW = 3600  # 1 hour


# ── Models ────────────────────────────────────────────────────────────

class SubmissionResponse(BaseModel):
    id: str
    message: str


class SubmissionStatus(BaseModel):
    id: str
    status: str  # 'pending', 'approved', 'rejected'
    submitted_at: str
    file_name: str
    file_type: str


# ── Helpers ───────────────────────────────────────────────────────────

def _sanitize_filename(name: str) -> str:
    """Remove path components and dangerous characters."""
    # Strip path separators
    name = name.replace("\\", "/").split("/")[-1]
    # Remove anything that isn't alphanumeric, dash, underscore, dot
    name = re.sub(r"[^\w\-.]", "_", name)
    # Collapse multiple dots/underscores
    name = re.sub(r"[_.]{2,}", "_", name)
    return name[:200]  # Truncate to reasonable length


def _check_rate_limit(ip: str) -> bool:
    """Returns True if request is allowed, False if rate-limited."""
    now = time.time()
    # Prune old entries
    _rate_limit_store[ip] = [t for t in _rate_limit_store[ip] if now - t < RATE_LIMIT_WINDOW]
    if len(_rate_limit_store[ip]) >= RATE_LIMIT_MAX:
        return False
    _rate_limit_store[ip].append(now)
    return True


def _is_dangerous_extension(filename: str) -> bool:
    """Check if filename has a dangerous extension."""
    lower = filename.lower()
    return any(lower.endswith(ext) for ext in DANGEROUS_EXTENSIONS)


def _is_dangerous_content(data: bytes) -> bool:
    """Check magic bytes for executable content."""
    for magic in DANGEROUS_MAGIC:
        if data[:len(magic)] == magic:
            return True
    return False


def _validate_magic_bytes(data: bytes) -> str | None:
    """Validate file content matches an allowed type. Returns MIME type or None."""
    for mime_type, signatures in ALLOWED_TYPES.items():
        for sig in signatures:
            if data[:len(sig)] == sig:
                return mime_type
    return None


async def _verify_captcha(token: str, secret: str) -> bool:
    """Verify hCaptcha token server-side."""
    if not secret:
        # Captcha not configured — allow (development mode)
        logger.warning("hCaptcha secret not configured — skipping verification")
        return True

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            "https://api.hcaptcha.com/siteverify",
            data={"secret": secret, "response": token},
        )
    if response.status_code != 200:
        return False
    result = response.json()
    return result.get("success", False)


def _get_submissions_blob_service(settings: Settings) -> BlobService:
    return BlobService(
        settings.AZURE_BLOB_CONNECTION_STRING,
        settings.BLOB_SUBMISSIONS_CONTAINER_NAME,
    )


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post("", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
async def submit_resource(
    request: Request,
    conn: Annotated[pyodbc.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: UploadFile = File(...),
    submitter_name: str = Form(""),
    submitter_email: str = Form(""),
    description: str = Form(""),
    resource_url: str = Form(""),
    captcha_token: str = Form(""),
) -> SubmissionResponse:
    """Accept a community resource submission with security validation."""

    client_ip = request.client.host if request.client else "unknown"

    # 1. Rate limiting
    if not _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many submissions. Please try again later.",
        )

    # 2. Captcha verification
    if not await _verify_captcha(captcha_token, settings.SUBMISSIONS_CAPTCHA_SECRET):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Captcha verification failed. Please try again.",
        )

    # 3. Read file content
    max_bytes = settings.SUBMISSIONS_MAX_FILE_SIZE_MB * 1024 * 1024
    data = await file.read()

    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.SUBMISSIONS_MAX_FILE_SIZE_MB} MB.",
        )

    if len(data) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file.",
        )

    filename = _sanitize_filename(file.filename or "unknown")

    # 4. SILENT DISCARD of dangerous files (attacker sees success)
    if _is_dangerous_extension(filename) or _is_dangerous_content(data):
        logger.warning(
            "SECURITY: Silently discarded dangerous upload from %s: %s (%d bytes)",
            client_ip, filename, len(data),
        )
        # Return fake success — attacker thinks upload worked
        fake_id = str(uuid.uuid4())
        return SubmissionResponse(
            id=fake_id,
            message="Thank you! Your submission has been received and is pending review.",
        )

    # 5. Validate magic bytes match allowed types
    detected_mime = _validate_magic_bytes(data)
    if detected_mime is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Accepted: JPEG, PNG, TIFF, GIF, WebP, PDF.",
        )

    # 6. Generate unique submission ID and blob path
    submission_id = str(uuid.uuid4())
    sha256 = hashlib.sha256(data).hexdigest()
    # Quarantine path: submissions/{date}/{uuid}/{sanitized_filename}
    date_prefix = datetime.now(UTC).strftime("%Y/%m/%d")
    blob_path = f"{date_prefix}/{submission_id}/{filename}"

    # 7. Upload to quarantine blob storage
    blob_service = _get_submissions_blob_service(settings)
    try:
        blob_service.upload_blob(blob_path, data, detected_mime)
    except Exception:
        logger.exception("Failed to upload submission %s", submission_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload failed. Please try again.",
        )

    # 8. Record metadata in SQL
    cursor = conn.cursor()
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Submissions' AND xtype='U')
        CREATE TABLE Submissions (
            SubmissionID NVARCHAR(36) PRIMARY KEY,
            SubmitterName NVARCHAR(200),
            SubmitterEmail NVARCHAR(255),
            Description NVARCHAR(MAX),
            ResourceURL NVARCHAR(2000),
            FileName NVARCHAR(255) NOT NULL,
            OriginalFileName NVARCHAR(500),
            FileSize BIGINT NOT NULL,
            MimeType NVARCHAR(100) NOT NULL,
            Sha256Hash NVARCHAR(64) NOT NULL,
            BlobPath NVARCHAR(500) NOT NULL,
            SubmitterIP NVARCHAR(45),
            Status NVARCHAR(20) DEFAULT 'pending',
            ReviewNotes NVARCHAR(MAX),
            ReviewedAt DATETIME2,
            ReviewedBy NVARCHAR(200),
            SubmittedAt DATETIME2 DEFAULT GETUTCDATE()
        )
    """)
    cursor.execute(
        """INSERT INTO Submissions
           (SubmissionID, SubmitterName, SubmitterEmail, Description, ResourceURL,
            FileName, OriginalFileName, FileSize, MimeType, Sha256Hash, BlobPath, SubmitterIP)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        submission_id,
        submitter_name[:200] if submitter_name else None,
        submitter_email[:255] if submitter_email else None,
        description[:5000] if description else None,
        resource_url[:2000] if resource_url else None,
        filename,
        file.filename,
        len(data),
        detected_mime,
        sha256,
        blob_path,
        client_ip,
    )
    conn.commit()

    logger.info(
        "Submission accepted: id=%s file=%s size=%d mime=%s ip=%s",
        submission_id, filename, len(data), detected_mime, client_ip,
    )

    return SubmissionResponse(
        id=submission_id,
        message="Thank you! Your submission has been received and is pending review.",
    )
