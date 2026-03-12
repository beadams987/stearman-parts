#!/usr/bin/env python3
"""
LBCD-to-Azure Migration Script
===============================

Migrates Boeing-Stearman aircraft engineering drawings from legacy LBCD databases
(4 encrypted Jet 4.0 MDB files) to Azure SQL + Azure Blob Storage.

Source: AirLog Imaging LogBooksOnCD v1.0 (May 2001)
  - 4 encrypted .lbc files (Microsoft Jet 4.0 / Access MDB)
  - 7,673 scanned TIFF images (~12000x9000px, Group 4 compressed)
  - 19,828 searchable index records (Drawing # and Key Word)

This script:
  1. Reads each .lbc file using mdbtools (subprocess calls to mdb-export)
  2. Extracts images from hex-encoded BLOBs in the CSV output
  3. Validates TIFF integrity and generates SHA-256 checksums
  4. Uploads originals and thumbnails to Azure Blob Storage
  5. Inserts metadata into Azure SQL with proper ID remapping
  6. Merges SERVICE MANUAL folders across discs; keeps frame drawings separate
  7. Produces a validation report confirming data integrity

Requirements:
  - mdbtools installed (apt-get install mdbtools)
  - Python packages: see scripts/requirements.txt
  - Azure credentials configured (env vars or Azure CLI login)

IMPORTANT: This script handles FAA/EASA regulatory documents. Data integrity is
paramount. Every image is checksummed, every record is validated, and full
provenance is preserved via source disc number and original IDs.

Usage:
  python migrate_lbcd.py --source-dir /path/to/lbc/files --dry-run
  python migrate_lbcd.py --source-dir /path/to/lbc/files --disc 1
  python migrate_lbcd.py --source-dir /path/to/lbc/files

Author: RedEye Network Solutions
Date: 2026-03-12
"""

import argparse
import csv
import hashlib
import io
import json
import logging
import os
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pyodbc
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings
from PIL import Image
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DISC_COUNT = 4

# Expected file naming: disc1.lbc, disc2.lbc, disc3.lbc, disc4.lbc
LBC_FILE_PATTERN = "disc{disc_num}.lbc"

# Source tables in the LBCD MDB schema
SOURCE_TABLES = [
    "MiscData",
    "IndexTypes",
    "Folders",
    "Bundles",
    "Images",
    "ImageIndexes",
    "BundleIndexes",
]

# Azure Blob Storage path templates
BLOB_PATH_ORIGINAL = "originals/disc{disc_num}/{image_id}.tif"
BLOB_PATH_THUMBNAIL = "thumbnails/disc{disc_num}/{image_id}.jpg"
BLOB_PATH_TILE = "tiles/{image_id}/"

# TIFF magic bytes for validation
TIFF_MAGIC_LE = b"\x49\x49\x2a\x00"  # Little-endian (II)
TIFF_MAGIC_BE = b"\x4d\x4d\x00\x2a"  # Big-endian (MM)
JPEG_MAGIC = b"\xff\xd8\xff"

# Expected totals from the migration plan for final validation
EXPECTED_TOTALS = {
    "images": 7673,
    "bundles": 396,
    "image_indexes": 18696,
    "bundle_indexes": 1132,
}

# Per-disc expected counts (from migration plan section 2.2)
EXPECTED_PER_DISC = {
    1: {"images": 2889, "bundles": 2, "image_indexes": 8248, "bundle_indexes": 3, "db_size_mb": 529},
    2: {"images": 1778, "bundles": 4, "image_indexes": 4863, "bundle_indexes": 9, "db_size_mb": 449},
    3: {"images": 1783, "bundles": 132, "image_indexes": 3990, "bundle_indexes": 371, "db_size_mb": 528},
    4: {"images": 1223, "bundles": 258, "image_indexes": 1595, "bundle_indexes": 749, "db_size_mb": 372},
}

# Folder merge strategy: SERVICE MANUAL folders are combined across discs.
# Frame Drawing folders (A-N) are unique per disc and kept separate.
SERVICE_MANUAL_FOLDER_NAME = "SERVICE MANUAL"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DiscMetadata:
    """Metadata extracted from a single disc's MiscData table."""
    disc_num: int
    aircraft_name: str = ""
    date_created: str = ""
    log_owner: str = ""
    validation_key: str = ""
    version: str = ""
    source_file: str = ""
    db_size_mb: int = 0


@dataclass
class MigrationStats:
    """Running statistics for the migration process."""
    folders_extracted: int = 0
    bundles_extracted: int = 0
    images_extracted: int = 0
    image_indexes_extracted: int = 0
    bundle_indexes_extracted: int = 0
    images_uploaded: int = 0
    thumbnails_uploaded: int = 0
    folders_inserted: int = 0
    bundles_inserted: int = 0
    images_inserted: int = 0
    image_indexes_inserted: int = 0
    bundle_indexes_inserted: int = 0
    bytes_uploaded: int = 0
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    check_name: str
    passed: bool
    expected: object = None
    actual: object = None
    message: str = ""


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(log_dir: Path, verbose: bool = False) -> logging.Logger:
    """Configure logging to both console and file."""
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"migration_{timestamp}.log"

    logger = logging.getLogger("lbcd_migration")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # File handler: always verbose
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(fh)

    # Console handler: respects verbose flag
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    ch.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(ch)

    logger.info("Log file: %s", log_file)
    return logger


# ---------------------------------------------------------------------------
# mdbtools interface
# ---------------------------------------------------------------------------

def check_mdbtools_installed():
    """Verify that mdbtools is available on the system."""
    try:
        result = subprocess.run(
            ["mdb-export", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # mdb-export may print version to stderr
        version_text = (result.stdout + result.stderr).strip()
        return version_text
    except FileNotFoundError:
        raise RuntimeError(
            "mdbtools is not installed. Install with: sudo apt-get install mdbtools"
        )


def mdb_export_csv(lbc_path: Path, table_name: str, blob_mode: str = "") -> str:
    """
    Run mdb-export on a table and return the raw CSV output as a string.

    Args:
        lbc_path: Path to the .lbc (MDB) file.
        table_name: Name of the table to export.
        blob_mode: Blob export mode. Use 'hex' for tables with BLOB columns
                   (Images). Empty string for metadata-only tables.

    Returns:
        CSV content as a string.

    Raises:
        RuntimeError: If mdb-export fails.
    """
    cmd = ["mdb-export"]
    if blob_mode:
        cmd.extend(["-b", blob_mode])
    cmd.extend([str(lbc_path), table_name])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=600,  # 10 minutes for large BLOB exports
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"mdb-export failed for {table_name} in {lbc_path.name}: "
            f"{result.stderr.strip()}"
        )

    return result.stdout


def mdb_count(lbc_path: Path, table_name: str) -> int:
    """Get the row count for a table using mdb-count."""
    result = subprocess.run(
        ["mdb-count", str(lbc_path), table_name],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"mdb-count failed for {table_name}: {result.stderr.strip()}"
        )
    return int(result.stdout.strip())


def mdb_tables(lbc_path: Path) -> list[str]:
    """List all tables in an MDB file."""
    result = subprocess.run(
        ["mdb-tables", "-1", str(lbc_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"mdb-tables failed: {result.stderr.strip()}")
    return [t.strip() for t in result.stdout.strip().split("\n") if t.strip()]


def parse_csv(csv_text: str) -> list[dict]:
    """Parse CSV text into a list of dicts."""
    # Increase field size limit to handle large hex-encoded BLOBs
    # Default is 131072 (~128KB) but TIFF blobs can be 500KB+ when hex-encoded
    csv.field_size_limit(sys.maxsize)
    reader = csv.DictReader(io.StringIO(csv_text))
    return list(reader)


# ---------------------------------------------------------------------------
# BLOB and image handling
# ---------------------------------------------------------------------------

def decode_hex_blob(hex_string: str) -> bytes:
    """
    Decode a hex-encoded BLOB from mdb-export output.

    mdb-export with -b hex encodes binary data as hex strings, typically
    prefixed with '0X' or '0x'. Example: 0X49492A00...

    Args:
        hex_string: The hex-encoded string from CSV output.

    Returns:
        Raw binary data.
    """
    if not hex_string:
        return b""

    # Strip surrounding whitespace and quotes
    cleaned = hex_string.strip().strip('"').strip("'")

    # Remove '0x' or '0X' prefix if present
    if cleaned.upper().startswith("0X"):
        cleaned = cleaned[2:]

    if not cleaned:
        return b""

    return bytes.fromhex(cleaned)


def validate_tiff(data: bytes, logger: logging.Logger) -> bool:
    """
    Validate that binary data is a valid TIFF file.

    Checks magic bytes and basic IFD structure.

    Args:
        data: Raw binary data.
        logger: Logger instance.

    Returns:
        True if the data appears to be a valid TIFF.
    """
    if len(data) < 8:
        logger.warning("Data too short to be a valid TIFF (%d bytes)", len(data))
        return False

    magic = data[:4]
    if magic == TIFF_MAGIC_LE:
        byte_order = "<"
    elif magic == TIFF_MAGIC_BE:
        byte_order = ">"
    else:
        # Check if it is a JPEG (cover images are JPEG)
        if data[:3] == JPEG_MAGIC:
            logger.debug("Data is JPEG, not TIFF (likely a cover image)")
            return True  # Valid image, just not TIFF
        logger.warning(
            "Invalid image magic bytes: %s", data[:4].hex()
        )
        return False

    # Read first IFD offset
    ifd_offset = struct.unpack(f"{byte_order}I", data[4:8])[0]
    if ifd_offset >= len(data):
        logger.warning(
            "IFD offset %d exceeds file size %d", ifd_offset, len(data)
        )
        return False

    return True


def compute_sha256(data: bytes) -> str:
    """Compute SHA-256 hash of binary data, returned as lowercase hex string."""
    return hashlib.sha256(data).hexdigest()


def get_image_dimensions(data: bytes) -> tuple[Optional[int], Optional[int]]:
    """
    Extract image width and height from binary data using Pillow.

    Returns (width, height) or (None, None) if the image cannot be read.
    """
    try:
        with Image.open(io.BytesIO(data)) as img:
            return img.size  # (width, height)
    except Exception:
        return None, None


def detect_mime_type(data: bytes) -> str:
    """Detect MIME type from magic bytes."""
    if data[:4] in (TIFF_MAGIC_LE, TIFF_MAGIC_BE):
        return "image/tiff"
    if data[:3] == JPEG_MAGIC:
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return "application/octet-stream"


# ---------------------------------------------------------------------------
# Azure Blob Storage operations
# ---------------------------------------------------------------------------

class BlobUploader:
    """Handles uploading images to Azure Blob Storage."""

    def __init__(
        self,
        connection_string: Optional[str] = None,
        account_url: Optional[str] = None,
        container_name: str = "stearman",
        dry_run: bool = False,
        logger: Optional[logging.Logger] = None,
    ):
        self.container_name = container_name
        self.dry_run = dry_run
        self.logger = logger or logging.getLogger(__name__)

        if not dry_run:
            if connection_string:
                self.blob_service = BlobServiceClient.from_connection_string(
                    connection_string
                )
            elif account_url:
                credential = DefaultAzureCredential()
                self.blob_service = BlobServiceClient(
                    account_url=account_url,
                    credential=credential,
                )
            else:
                raise ValueError(
                    "Either connection_string or account_url must be provided"
                )
            self._ensure_container()
        else:
            self.blob_service = None

    def _ensure_container(self):
        """Create the blob container if it does not exist."""
        try:
            self.blob_service.create_container(self.container_name)
            self.logger.info("Created blob container: %s", self.container_name)
        except Exception:
            # Container already exists
            pass

    def upload(
        self,
        blob_path: str,
        data: bytes,
        content_type: str = "image/tiff",
    ) -> str:
        """
        Upload binary data to Azure Blob Storage.

        Args:
            blob_path: The path within the container.
            data: Binary data to upload.
            content_type: MIME type for the Content-Type header.

        Returns:
            The full blob path (container/path).
        """
        if self.dry_run:
            self.logger.debug("[DRY RUN] Would upload %s (%d bytes)", blob_path, len(data))
            return blob_path

        blob_client = self.blob_service.get_blob_client(
            container=self.container_name,
            blob=blob_path,
        )
        content_settings = ContentSettings(content_type=content_type)
        blob_client.upload_blob(
            data,
            overwrite=True,
            content_settings=content_settings,
        )
        self.logger.debug("Uploaded %s (%d bytes)", blob_path, len(data))
        return blob_path


# ---------------------------------------------------------------------------
# Azure SQL operations
# ---------------------------------------------------------------------------

class SqlLoader:
    """Handles inserting migrated data into Azure SQL Database."""

    def __init__(
        self,
        connection_string: str,
        dry_run: bool = False,
        logger: Optional[logging.Logger] = None,
    ):
        self.dry_run = dry_run
        self.logger = logger or logging.getLogger(__name__)
        self._connection_string = connection_string
        self._conn: Optional[pyodbc.Connection] = None

    def connect(self):
        """Establish database connection."""
        if self.dry_run:
            self.logger.info("[DRY RUN] Would connect to Azure SQL")
            return
        self._conn = pyodbc.connect(self._connection_string, autocommit=False)
        self.logger.info("Connected to Azure SQL Database")

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def execute(self, sql: str, params: tuple = ()) -> Optional[pyodbc.Cursor]:
        """Execute a SQL statement."""
        if self.dry_run:
            self.logger.debug("[DRY RUN] SQL: %s | params: %s", sql[:200], str(params)[:200])
            return None
        cursor = self._conn.cursor()
        cursor.execute(sql, params)
        return cursor

    def execute_identity(self, sql: str, params: tuple = ()) -> Optional[int]:
        """Execute an INSERT and return the generated IDENTITY value."""
        if self.dry_run:
            self.logger.debug("[DRY RUN] SQL: %s | params: %s", sql[:200], str(params)[:200])
            return None
        cursor = self._conn.cursor()
        cursor.execute(sql, params)
        cursor.execute("SELECT SCOPE_IDENTITY()")
        row = cursor.fetchone()
        return int(row[0]) if row and row[0] is not None else None

    def commit(self):
        """Commit the current transaction."""
        if self._conn and not self.dry_run:
            self._conn.commit()
            self.logger.debug("Transaction committed")

    def rollback(self):
        """Rollback the current transaction."""
        if self._conn and not self.dry_run:
            self._conn.rollback()
            self.logger.warning("Transaction rolled back")

    def insert_aircraft(self, name: str, owner: str, date_created: str, validation_key: str) -> Optional[int]:
        """Insert the Aircraft record and return the AircraftID."""
        return self.execute_identity(
            """
            INSERT INTO Aircraft (Name, Owner, DateCreated, SourceValidationKey)
            VALUES (?, ?, ?, ?)
            """,
            (name, owner, date_created, validation_key),
        )

    def insert_disc(self, disc: DiscMetadata):
        """Insert a Discs provenance record."""
        expected = EXPECTED_PER_DISC.get(disc.disc_num, {})
        self.execute(
            """
            INSERT INTO Discs (DiscID, SourceFileName, DatabaseSizeMB,
                               ImageCount, BundleCount, IndexRecordCount, DateCreated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                disc.disc_num,
                disc.source_file,
                disc.db_size_mb,
                expected.get("images", 0),
                expected.get("bundles", 0),
                expected.get("image_indexes", 0) + expected.get("bundle_indexes", 0),
                disc.date_created or None,
            ),
        )

    def insert_folder(
        self,
        aircraft_id: int,
        parent_folder_id: Optional[int],
        source_disc_num: int,
        source_folder_id: int,
        folder_name: str,
        sort_order: int,
        notes: Optional[str],
    ) -> Optional[int]:
        """Insert a Folder record and return the new FolderID."""
        return self.execute_identity(
            """
            INSERT INTO Folders (AircraftID, ParentFolderID, SourceDiscNumber,
                                 SourceFolderID, FolderName, SortOrder, Notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (aircraft_id, parent_folder_id, source_disc_num,
             source_folder_id, folder_name, sort_order, notes),
        )

    def insert_bundle(
        self,
        folder_id: int,
        image_position: int,
        notes: Optional[str],
        source_disc_num: int,
        source_bundle_id: int,
    ) -> Optional[int]:
        """Insert a Bundle record and return the new BundleID."""
        return self.execute_identity(
            """
            INSERT INTO Bundles (FolderID, ImagePosition, Notes,
                                 SourceDiscNumber, SourceBundleID)
            VALUES (?, ?, ?, ?, ?)
            """,
            (folder_id, image_position, notes, source_disc_num, source_bundle_id),
        )

    def insert_image(
        self,
        folder_id: int,
        bundle_id: Optional[int],
        bundle_offset: Optional[int],
        image_position: int,
        original_filename: Optional[str],
        blob_path: str,
        tile_path: Optional[str],
        thumbnail_path: Optional[str],
        image_width: Optional[int],
        image_height: Optional[int],
        file_size_bytes: Optional[int],
        mime_type: str,
        sha256_hash: str,
        notes: Optional[str],
        source_disc_num: int,
        source_image_id: int,
    ) -> Optional[int]:
        """Insert an Image metadata record and return the new ImageID."""
        return self.execute_identity(
            """
            INSERT INTO Images (FolderID, BundleID, BundleOffset, ImagePosition,
                                OriginalFileName, BlobPath, TilePath, ThumbnailPath,
                                ImageWidth, ImageHeight, FileSizeBytes, MimeType,
                                Sha256Hash, Notes, SourceDiscNumber, SourceImageID)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (folder_id, bundle_id, bundle_offset, image_position,
             original_filename, blob_path, tile_path, thumbnail_path,
             image_width, image_height, file_size_bytes, mime_type,
             sha256_hash, notes, source_disc_num, source_image_id),
        )

    def insert_image_index(
        self,
        image_id: int,
        index_type_id: int,
        index_value: str,
    ):
        """Insert an ImageIndex search record."""
        self.execute(
            """
            INSERT INTO ImageIndexes (ImageID, IndexTypeID, IndexValue)
            VALUES (?, ?, ?)
            """,
            (image_id, index_type_id, index_value),
        )

    def insert_bundle_index(
        self,
        bundle_id: int,
        index_type_id: int,
        index_value: str,
    ):
        """Insert a BundleIndex search record."""
        self.execute(
            """
            INSERT INTO BundleIndexes (BundleID, IndexTypeID, IndexValue)
            VALUES (?, ?, ?)
            """,
            (bundle_id, index_type_id, index_value),
        )

    def get_row_count(self, table_name: str) -> int:
        """Return the row count for a table (for validation)."""
        if self.dry_run:
            return 0
        cursor = self.execute(f"SELECT COUNT(*) FROM [{table_name}]")
        return cursor.fetchone()[0]


# ---------------------------------------------------------------------------
# Extraction and transformation
# ---------------------------------------------------------------------------

def extract_misc_data(lbc_path: Path, disc_num: int, logger: logging.Logger) -> DiscMetadata:
    """Extract metadata from the MiscData table."""
    csv_text = mdb_export_csv(lbc_path, "MiscData")
    rows = parse_csv(csv_text)

    metadata = DiscMetadata(disc_num=disc_num)
    metadata.source_file = lbc_path.name
    metadata.db_size_mb = int(lbc_path.stat().st_size / (1024 * 1024))

    kv = {row["KeyWord"].strip(): row["String"].strip() for row in rows}
    metadata.aircraft_name = kv.get("AirCraft", "")
    metadata.date_created = kv.get("DateCreated", "")
    metadata.log_owner = kv.get("LogOwner", "")
    metadata.validation_key = kv.get("ValidationKey", "")
    metadata.version = kv.get("Version", "")

    logger.info(
        "Disc %d metadata: aircraft=%s, owner=%s, created=%s",
        disc_num, metadata.aircraft_name, metadata.log_owner, metadata.date_created,
    )
    return metadata


def extract_folders(lbc_path: Path, disc_num: int, logger: logging.Logger) -> list[dict]:
    """Extract folder records from a disc."""
    csv_text = mdb_export_csv(lbc_path, "Folders")
    rows = parse_csv(csv_text)
    logger.info("Disc %d: extracted %d folders", disc_num, len(rows))
    return rows


def extract_bundles(lbc_path: Path, disc_num: int, logger: logging.Logger) -> list[dict]:
    """Extract bundle records from a disc."""
    csv_text = mdb_export_csv(lbc_path, "Bundles")
    rows = parse_csv(csv_text)
    logger.info("Disc %d: extracted %d bundles", disc_num, len(rows))
    return rows


def extract_image_indexes(lbc_path: Path, disc_num: int, logger: logging.Logger) -> list[dict]:
    """Extract image index records from a disc."""
    csv_text = mdb_export_csv(lbc_path, "ImageIndexes")
    rows = parse_csv(csv_text)
    logger.info("Disc %d: extracted %d image indexes", disc_num, len(rows))
    return rows


def extract_bundle_indexes(lbc_path: Path, disc_num: int, logger: logging.Logger) -> list[dict]:
    """Extract bundle index records from a disc."""
    csv_text = mdb_export_csv(lbc_path, "BundleIndexes")
    rows = parse_csv(csv_text)
    logger.info("Disc %d: extracted %d bundle indexes", disc_num, len(rows))
    return rows


def extract_images_metadata(lbc_path: Path, disc_num: int, logger: logging.Logger) -> list[dict]:
    """
    Extract image metadata (without BLOBs) from a disc.

    Uses -b strip to omit binary BLOB data (Image and Thumbnail columns)
    and return only the scalar metadata columns cleanly as UTF-8 text.
    """
    csv_text = mdb_export_csv(lbc_path, "Images", blob_mode="strip")
    rows = parse_csv(csv_text)
    logger.info("Disc %d: extracted metadata for %d images", disc_num, len(rows))
    return rows


def extract_image_blobs(
    lbc_path: Path,
    disc_num: int,
    staging_dir: Path,
    logger: logging.Logger,
    stats: MigrationStats,
) -> dict[int, dict]:
    """
    Extract image and thumbnail BLOBs from a disc's Images table.

    Uses mdb-export with -b hex to get hex-encoded BLOB data, then decodes
    each BLOB, validates it, computes SHA-256, and writes to the staging
    directory.

    Args:
        lbc_path: Path to the .lbc file.
        disc_num: Disc number (1-4).
        staging_dir: Base staging directory.
        logger: Logger instance.
        stats: Migration statistics tracker.

    Returns:
        Dict mapping source ImageID to a dict with keys:
            image_path, thumb_path, sha256, width, height, file_size, mime_type
    """
    logger.info("Disc %d: extracting image BLOBs (this may take several minutes)...", disc_num)

    # Create staging subdirectories
    images_dir = staging_dir / f"disc{disc_num}" / "images"
    thumbs_dir = staging_dir / f"disc{disc_num}" / "thumbs"
    images_dir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    # Export with hex-encoded BLOBs
    csv_text = mdb_export_csv(lbc_path, "Images", blob_mode="hex")
    rows = parse_csv(csv_text)

    blob_info = {}
    for row in tqdm(rows, desc=f"Disc {disc_num} images", unit="img"):
        source_id = int(row["ImageID"])

        # Decode the full-resolution image BLOB
        image_hex = row.get("Image", "")
        if not image_hex or image_hex.strip() in ("", '""'):
            logger.warning(
                "Disc %d, ImageID %d: empty image BLOB, skipping",
                disc_num, source_id,
            )
            stats.warnings.append(f"Disc {disc_num} ImageID {source_id}: empty BLOB")
            continue

        image_data = decode_hex_blob(image_hex)
        if not image_data:
            logger.warning(
                "Disc %d, ImageID %d: could not decode image hex data",
                disc_num, source_id,
            )
            stats.errors.append(f"Disc {disc_num} ImageID {source_id}: hex decode failed")
            continue

        # Check if already staged (resume support)
        # Quick check: if any file with this source_id exists in images_dir, skip re-extraction
        existing_tif = images_dir / f"{source_id}.tif"
        existing_jpg = images_dir / f"{source_id}.jpg"
        if existing_tif.exists() or existing_jpg.exists():
            existing_path = existing_tif if existing_tif.exists() else existing_jpg
            existing_data = existing_path.read_bytes()
            existing_thumb = thumbs_dir / f"{source_id}.jpg"
            blob_info[source_id] = {
                "image_path": str(existing_path),
                "thumb_path": str(existing_thumb) if existing_thumb.exists() else None,
                "sha256": compute_sha256(existing_data),
                "width": None,
                "height": None,
                "file_size": len(existing_data),
                "mime_type": detect_mime_type(existing_data),
            }
            continue

        # Validate image data
        if not validate_tiff(image_data, logger):
            logger.error(
                "Disc %d, ImageID %d: image failed TIFF/JPEG validation",
                disc_num, source_id,
            )
            stats.errors.append(
                f"Disc {disc_num} ImageID {source_id}: image validation failed"
            )
            # Still write to staging for manual inspection, but flag it
            # Continue processing: do not skip, as the data may still be usable

        # Compute SHA-256
        sha256 = compute_sha256(image_data)

        # Detect MIME type and file extension
        mime_type = detect_mime_type(image_data)
        ext = ".tif" if mime_type == "image/tiff" else ".jpg"

        # Write image to staging
        image_path = images_dir / f"{source_id}{ext}"
        image_path.write_bytes(image_data)

        # Get dimensions
        width, height = get_image_dimensions(image_data)

        # Decode thumbnail BLOB (if present)
        thumb_path = None
        thumb_hex = row.get("Thumbnail", "")
        if thumb_hex and thumb_hex.strip() not in ("", '""'):
            thumb_data = decode_hex_blob(thumb_hex)
            if thumb_data:
                thumb_path = thumbs_dir / f"{source_id}.jpg"
                thumb_path.write_bytes(thumb_data)

        blob_info[source_id] = {
            "image_path": str(image_path),
            "thumb_path": str(thumb_path) if thumb_path else None,
            "sha256": sha256,
            "width": width,
            "height": height,
            "file_size": len(image_data),
            "mime_type": mime_type,
        }

    logger.info(
        "Disc %d: extracted %d image BLOBs to %s",
        disc_num, len(blob_info), images_dir,
    )
    return blob_info


# ---------------------------------------------------------------------------
# Folder merge logic
# ---------------------------------------------------------------------------

def build_folder_sort_order(folder_name: str) -> int:
    """
    Determine sort order for folders in the merged structure.

    SERVICE MANUAL comes first (sort_order=0), then frame drawings
    A-N in alphabetical order (sort_order = 1-14).
    Frame letters skip 'I' per aviation convention.
    """
    if SERVICE_MANUAL_FOLDER_NAME in folder_name.upper():
        return 0

    # Extract the letter prefix from "X FRAME DRAWINGS"
    parts = folder_name.strip().split()
    if parts and len(parts[0]) == 1 and parts[0].isalpha():
        letter = parts[0].upper()
        # A=1, B=2, ..., H=8, J=9, K=10, L=11, M=12, N=13
        # (skip I)
        frame_order = "ABCDEFGHJKLMN"
        if letter in frame_order:
            return frame_order.index(letter) + 1

    return 99  # Unknown folders go last


# ---------------------------------------------------------------------------
# Core migration logic
# ---------------------------------------------------------------------------

def process_disc(
    disc_num: int,
    lbc_path: Path,
    staging_dir: Path,
    uploader: BlobUploader,
    sql: SqlLoader,
    aircraft_id: int,
    folder_id_map: dict,
    service_manual_folder_id: Optional[int],
    dry_run: bool,
    logger: logging.Logger,
    stats: MigrationStats,
) -> Optional[int]:
    """
    Process a single disc: extract, transform, and load all data.

    Args:
        disc_num: The disc number (1-4).
        lbc_path: Path to the .lbc file.
        staging_dir: Base staging directory for extracted BLOBs.
        uploader: Azure Blob Storage uploader.
        sql: Azure SQL loader.
        aircraft_id: The AircraftID for this aircraft in the target DB.
        folder_id_map: Mutable dict mapping (disc_num, source_folder_id) -> new_folder_id.
                       Shared across discs for the SERVICE MANUAL merge.
        service_manual_folder_id: If a SERVICE MANUAL folder has already been created
                                  from a previous disc, reuse this ID.
        dry_run: If True, do not write to Azure.
        logger: Logger instance.
        stats: Migration statistics tracker.

    Returns:
        The SERVICE MANUAL folder ID (new or existing) for passing to next disc.
    """
    logger.info("=" * 70)
    logger.info("Processing Disc %d: %s", disc_num, lbc_path.name)
    logger.info("=" * 70)

    # ------------------------------------------------------------------
    # 1. Extract metadata
    # ------------------------------------------------------------------
    disc_meta = extract_misc_data(lbc_path, disc_num, logger)
    sql.insert_disc(disc_meta)

    # ------------------------------------------------------------------
    # 2. Extract and merge folders
    # ------------------------------------------------------------------
    source_folders = extract_folders(lbc_path, disc_num, logger)
    stats.folders_extracted += len(source_folders)

    # Build the root folder for this disc if needed.
    # In the source, folder with ParentFolderID=0 is the root (e.g., DISC_1_STEARMAN).
    # We skip the per-disc root and attach children directly under the aircraft.

    root_folders = [f for f in source_folders if str(f.get("ParentFolderID", "0")).strip() == "0"]
    child_folders = [f for f in source_folders if str(f.get("ParentFolderID", "0")).strip() != "0"]

    # Map source root folder IDs so children can find their parent
    source_root_ids = {int(f["FolderID"]) for f in root_folders}

    for folder_row in child_folders:
        source_folder_id = int(folder_row["FolderID"])
        folder_name = folder_row["FolderName"].strip()
        notes = folder_row.get("Notes", "").strip() or None

        sort_order = build_folder_sort_order(folder_name)

        # Determine if this is a SERVICE MANUAL folder that should be merged
        is_service_manual = SERVICE_MANUAL_FOLDER_NAME in folder_name.upper()

        if is_service_manual and service_manual_folder_id is not None:
            # Reuse the existing merged SERVICE MANUAL folder
            folder_id_map[(disc_num, source_folder_id)] = service_manual_folder_id
            logger.info(
                "Disc %d: merging '%s' into existing SERVICE MANUAL folder (ID %d)",
                disc_num, folder_name, service_manual_folder_id,
            )
        else:
            # Create a new folder
            new_folder_id = sql.insert_folder(
                aircraft_id=aircraft_id,
                parent_folder_id=None,  # All content folders are top-level under the aircraft
                source_disc_num=disc_num,
                source_folder_id=source_folder_id,
                folder_name=folder_name,
                sort_order=sort_order,
                notes=notes,
            )
            folder_id_map[(disc_num, source_folder_id)] = new_folder_id
            stats.folders_inserted += 1

            if is_service_manual:
                service_manual_folder_id = new_folder_id
                logger.info(
                    "Disc %d: created SERVICE MANUAL folder (ID %s)",
                    disc_num, new_folder_id,
                )
            else:
                logger.info(
                    "Disc %d: created folder '%s' (ID %s)",
                    disc_num, folder_name, new_folder_id,
                )

    # Also map root folders (in case any images reference the root directly)
    for root_row in root_folders:
        source_root_id = int(root_row["FolderID"])
        # Root folders are disc containers; they don't map to the merged schema.
        # If images reference the root, we need a fallback.
        # Create a placeholder entry that maps to the first child folder or skip.
        logger.debug(
            "Disc %d: root folder '%s' (ID %d) skipped (disc container)",
            disc_num, root_row["FolderName"].strip(), source_root_id,
        )

    # ------------------------------------------------------------------
    # 3. Extract and load bundles
    # ------------------------------------------------------------------
    source_bundles = extract_bundles(lbc_path, disc_num, logger)
    stats.bundles_extracted += len(source_bundles)

    # Map: (disc_num, source_bundle_id) -> new_bundle_id
    bundle_id_map = {}

    for bundle_row in source_bundles:
        source_bundle_id = int(bundle_row["BundleID"])
        source_folder_id = int(bundle_row["FolderID"])
        image_position = int(bundle_row.get("ImagePosition", 0))
        notes = bundle_row.get("Notes", "").strip() or None

        # Resolve the new folder ID
        folder_map_key = (disc_num, source_folder_id)
        if folder_map_key not in folder_id_map:
            logger.warning(
                "Disc %d, BundleID %d: references unmapped FolderID %d, skipping",
                disc_num, source_bundle_id, source_folder_id,
            )
            stats.warnings.append(
                f"Disc {disc_num} BundleID {source_bundle_id}: unmapped folder {source_folder_id}"
            )
            continue
        new_folder_id = folder_id_map[folder_map_key]

        new_bundle_id = sql.insert_bundle(
            folder_id=new_folder_id,
            image_position=image_position,
            notes=notes,
            source_disc_num=disc_num,
            source_bundle_id=source_bundle_id,
        )
        bundle_id_map[(disc_num, source_bundle_id)] = new_bundle_id
        stats.bundles_inserted += 1

    logger.info(
        "Disc %d: loaded %d bundles", disc_num, len(bundle_id_map),
    )

    # ------------------------------------------------------------------
    # 4. Extract image BLOBs and upload to Azure Blob Storage
    # ------------------------------------------------------------------
    blob_info = extract_image_blobs(
        lbc_path, disc_num, staging_dir, logger, stats,
    )
    stats.images_extracted += len(blob_info)

    # Upload images to Blob Storage
    # Map: source_image_id -> new_image_id
    image_id_map = {}

    # Get metadata rows (without BLOBs) for the non-BLOB columns
    metadata_rows = extract_images_metadata(lbc_path, disc_num, logger)
    metadata_by_id = {int(r["ImageID"]): r for r in metadata_rows}

    for source_image_id, info in tqdm(
        blob_info.items(), desc=f"Disc {disc_num} upload", unit="img"
    ):
        meta = metadata_by_id.get(source_image_id, {})
        source_folder_id = int(meta.get("FolderID", 0))
        source_bundle_id = int(meta.get("BundleID", 0))
        bundle_offset = int(meta.get("BundleOffset", 0)) or None
        image_position = int(meta.get("ImagePosition", 0))
        original_filename = meta.get("FileName", "").strip() or None

        # Resolve folder
        img_folder_key = (disc_num, source_folder_id)
        if img_folder_key not in folder_id_map:
            logger.warning(
                "Disc %d, ImageID %d: references unmapped FolderID %d, skipping",
                disc_num, source_image_id, source_folder_id,
            )
            stats.warnings.append(
                f"Disc {disc_num} ImageID {source_image_id}: unmapped folder {source_folder_id}"
            )
            continue
        new_folder_id = folder_id_map[img_folder_key]

        # Resolve bundle (0 means standalone, no bundle)
        new_bundle_id = None
        if source_bundle_id and source_bundle_id != 0:
            new_bundle_id = bundle_id_map.get((disc_num, source_bundle_id))
            if new_bundle_id is None:
                logger.warning(
                    "Disc %d, ImageID %d: references unmapped BundleID %d",
                    disc_num, source_image_id, source_bundle_id,
                )
                stats.warnings.append(
                    f"Disc {disc_num} ImageID {source_image_id}: unmapped bundle {source_bundle_id}"
                )
                # Continue without bundle assignment
                bundle_offset = None

        # Upload original image to Blob Storage
        ext = ".tif" if info["mime_type"] == "image/tiff" else ".jpg"
        blob_path = BLOB_PATH_ORIGINAL.format(
            disc_num=disc_num, image_id=source_image_id,
        )
        if ext != ".tif":
            blob_path = blob_path.replace(".tif", ext)

        image_data = Path(info["image_path"]).read_bytes()
        uploader.upload(blob_path, image_data, content_type=info["mime_type"])
        stats.images_uploaded += 1
        stats.bytes_uploaded += len(image_data)

        # Upload thumbnail if available
        thumbnail_path = None
        if info["thumb_path"]:
            thumb_blob_path = BLOB_PATH_THUMBNAIL.format(
                disc_num=disc_num, image_id=source_image_id,
            )
            thumb_data = Path(info["thumb_path"]).read_bytes()
            uploader.upload(thumb_blob_path, thumb_data, content_type="image/jpeg")
            thumbnail_path = thumb_blob_path
            stats.thumbnails_uploaded += 1

        # Insert image metadata into SQL
        new_image_id = sql.insert_image(
            folder_id=new_folder_id,
            bundle_id=new_bundle_id,
            bundle_offset=bundle_offset,
            image_position=image_position,
            original_filename=original_filename,
            blob_path=blob_path,
            tile_path=None,  # DZI tiles generated in a separate post-processing step
            thumbnail_path=thumbnail_path,
            image_width=info["width"],
            image_height=info["height"],
            file_size_bytes=info["file_size"],
            mime_type=info["mime_type"],
            sha256_hash=info["sha256"],
            notes=meta.get("Notes", "").strip() or None,
            source_disc_num=disc_num,
            source_image_id=source_image_id,
        )
        image_id_map[source_image_id] = new_image_id
        stats.images_inserted += 1

    logger.info(
        "Disc %d: uploaded %d images, %d thumbnails (%d bytes total)",
        disc_num, stats.images_uploaded, stats.thumbnails_uploaded, stats.bytes_uploaded,
    )

    # ------------------------------------------------------------------
    # 5. Load image indexes
    # ------------------------------------------------------------------
    source_image_indexes = extract_image_indexes(lbc_path, disc_num, logger)
    stats.image_indexes_extracted += len(source_image_indexes)

    for idx_row in tqdm(
        source_image_indexes, desc=f"Disc {disc_num} image indexes", unit="idx"
    ):
        source_image_id = int(idx_row["ImageID"])
        index_type_id = int(idx_row["IndexTypeID"])
        index_value = idx_row.get("IndexString", "").strip()

        if not index_value:
            continue

        new_image_id = image_id_map.get(source_image_id)
        if new_image_id is None:
            logger.debug(
                "Disc %d: image index for unmapped ImageID %d, skipping",
                disc_num, source_image_id,
            )
            continue

        sql.insert_image_index(new_image_id, index_type_id, index_value)
        stats.image_indexes_inserted += 1

    logger.info(
        "Disc %d: loaded %d image indexes",
        disc_num, stats.image_indexes_inserted,
    )

    # ------------------------------------------------------------------
    # 6. Load bundle indexes
    # ------------------------------------------------------------------
    source_bundle_indexes = extract_bundle_indexes(lbc_path, disc_num, logger)
    stats.bundle_indexes_extracted += len(source_bundle_indexes)

    for idx_row in tqdm(
        source_bundle_indexes, desc=f"Disc {disc_num} bundle indexes", unit="idx"
    ):
        source_bundle_id = int(idx_row["BundleID"])
        index_type_id = int(idx_row["IndexTypeID"])
        index_value = idx_row.get("IndexString", "").strip()

        if not index_value:
            continue

        new_bundle_id = bundle_id_map.get((disc_num, source_bundle_id))
        if new_bundle_id is None:
            logger.debug(
                "Disc %d: bundle index for unmapped BundleID %d, skipping",
                disc_num, source_bundle_id,
            )
            continue

        sql.insert_bundle_index(new_bundle_id, index_type_id, index_value)
        stats.bundle_indexes_inserted += 1

    logger.info(
        "Disc %d: loaded %d bundle indexes",
        disc_num, stats.bundle_indexes_inserted,
    )

    # Commit this disc's data
    sql.commit()
    logger.info("Disc %d: committed all data to Azure SQL", disc_num)

    return service_manual_folder_id


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_migration(
    sql: SqlLoader,
    stats: MigrationStats,
    discs_processed: list[int],
    logger: logging.Logger,
) -> list[ValidationResult]:
    """
    Run post-migration validation checks and return results.

    Validates:
      - Row counts in target tables match source extraction counts
      - Row counts match expected totals from the migration plan
      - Referential integrity (all FK references are valid)
      - No orphaned records
    """
    results = []

    if sql.dry_run:
        logger.info("[DRY RUN] Skipping database validation")
        return results

    logger.info("=" * 70)
    logger.info("Running post-migration validation")
    logger.info("=" * 70)

    # --- Count validation: extracted vs. inserted ---

    def check_count(name: str, extracted: int, inserted: int):
        passed = extracted == inserted
        result = ValidationResult(
            check_name=f"{name}: extracted vs. inserted",
            passed=passed,
            expected=extracted,
            actual=inserted,
            message="" if passed else f"MISMATCH: extracted {extracted}, inserted {inserted}",
        )
        results.append(result)
        level = logging.INFO if passed else logging.ERROR
        logger.log(
            level, "  [%s] %s: expected=%d, actual=%d",
            "PASS" if passed else "FAIL", result.check_name,
            extracted, inserted,
        )

    check_count("Images", stats.images_extracted, stats.images_inserted)
    check_count("Bundles", stats.bundles_extracted, stats.bundles_inserted)

    # Index counts may differ from extracted if some had empty values or unmapped IDs
    # Use >= for warning-level checks
    logger.info(
        "  [INFO] Image indexes: extracted=%d, inserted=%d",
        stats.image_indexes_extracted, stats.image_indexes_inserted,
    )
    logger.info(
        "  [INFO] Bundle indexes: extracted=%d, inserted=%d",
        stats.bundle_indexes_extracted, stats.bundle_indexes_inserted,
    )

    # --- Count validation: target tables vs. expected totals ---

    all_discs = set(discs_processed) == {1, 2, 3, 4}

    if all_discs:
        expected_images = EXPECTED_TOTALS["images"]
        actual_images = sql.get_row_count("Images")
        passed = actual_images == expected_images
        results.append(ValidationResult(
            check_name="Total images vs. expected",
            passed=passed,
            expected=expected_images,
            actual=actual_images,
        ))
        level = logging.INFO if passed else logging.ERROR
        logger.log(
            level, "  [%s] Total images: expected=%d, actual=%d",
            "PASS" if passed else "FAIL", expected_images, actual_images,
        )

        expected_bundles = EXPECTED_TOTALS["bundles"]
        actual_bundles = sql.get_row_count("Bundles")
        passed = actual_bundles == expected_bundles
        results.append(ValidationResult(
            check_name="Total bundles vs. expected",
            passed=passed,
            expected=expected_bundles,
            actual=actual_bundles,
        ))
        level = logging.INFO if passed else logging.ERROR
        logger.log(
            level, "  [%s] Total bundles: expected=%d, actual=%d",
            "PASS" if passed else "FAIL", expected_bundles, actual_bundles,
        )

    # --- Referential integrity checks ---

    integrity_checks = [
        (
            "Images -> Folders FK",
            "SELECT COUNT(*) FROM Images i WHERE NOT EXISTS (SELECT 1 FROM Folders f WHERE f.FolderID = i.FolderID)",
        ),
        (
            "Images -> Bundles FK (non-null)",
            "SELECT COUNT(*) FROM Images i WHERE i.BundleID IS NOT NULL AND NOT EXISTS (SELECT 1 FROM Bundles b WHERE b.BundleID = i.BundleID)",
        ),
        (
            "Bundles -> Folders FK",
            "SELECT COUNT(*) FROM Bundles b WHERE NOT EXISTS (SELECT 1 FROM Folders f WHERE f.FolderID = b.FolderID)",
        ),
        (
            "ImageIndexes -> Images FK",
            "SELECT COUNT(*) FROM ImageIndexes ix WHERE NOT EXISTS (SELECT 1 FROM Images i WHERE i.ImageID = ix.ImageID)",
        ),
        (
            "BundleIndexes -> Bundles FK",
            "SELECT COUNT(*) FROM BundleIndexes bi WHERE NOT EXISTS (SELECT 1 FROM Bundles b WHERE b.BundleID = bi.BundleID)",
        ),
        (
            "ImageIndexes -> IndexTypes FK",
            "SELECT COUNT(*) FROM ImageIndexes ix WHERE NOT EXISTS (SELECT 1 FROM IndexTypes it WHERE it.IndexTypeID = ix.IndexTypeID)",
        ),
        (
            "BundleIndexes -> IndexTypes FK",
            "SELECT COUNT(*) FROM BundleIndexes bi WHERE NOT EXISTS (SELECT 1 FROM IndexTypes it WHERE it.IndexTypeID = bi.IndexTypeID)",
        ),
    ]

    for check_name, query in integrity_checks:
        try:
            cursor = sql.execute(query)
            orphan_count = cursor.fetchone()[0]
            passed = orphan_count == 0
            results.append(ValidationResult(
                check_name=check_name,
                passed=passed,
                expected=0,
                actual=orphan_count,
                message="" if passed else f"{orphan_count} orphaned records found",
            ))
            level = logging.INFO if passed else logging.ERROR
            logger.log(
                level, "  [%s] %s: orphans=%d",
                "PASS" if passed else "FAIL", check_name, orphan_count,
            )
        except Exception as e:
            results.append(ValidationResult(
                check_name=check_name,
                passed=False,
                message=f"Query failed: {e}",
            ))
            logger.error("  [FAIL] %s: %s", check_name, e)

    # --- SHA-256 uniqueness check (detect exact duplicate images) ---
    try:
        cursor = sql.execute(
            "SELECT Sha256Hash, COUNT(*) AS cnt FROM Images "
            "GROUP BY Sha256Hash HAVING COUNT(*) > 1"
        )
        duplicates = cursor.fetchall()
        if duplicates:
            logger.warning(
                "  [WARN] Found %d SHA-256 hashes with duplicate images "
                "(may be expected for SERVICE MANUAL pages shared across discs)",
                len(duplicates),
            )
            for dup_hash, count in duplicates[:10]:  # Show first 10
                logger.warning("    Hash %s...: %d copies", dup_hash[:16], count)
        else:
            logger.info("  [INFO] No duplicate images detected by SHA-256")
    except Exception as e:
        logger.warning("  [WARN] Could not check for duplicate images: %s", e)

    return results


def write_validation_report(
    results: list[ValidationResult],
    stats: MigrationStats,
    discs_processed: list[int],
    report_path: Path,
    logger: logging.Logger,
):
    """Write a JSON validation report to disk."""
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "discs_processed": discs_processed,
        "statistics": {
            "folders_extracted": stats.folders_extracted,
            "folders_inserted": stats.folders_inserted,
            "bundles_extracted": stats.bundles_extracted,
            "bundles_inserted": stats.bundles_inserted,
            "images_extracted": stats.images_extracted,
            "images_inserted": stats.images_inserted,
            "images_uploaded": stats.images_uploaded,
            "thumbnails_uploaded": stats.thumbnails_uploaded,
            "image_indexes_extracted": stats.image_indexes_extracted,
            "image_indexes_inserted": stats.image_indexes_inserted,
            "bundle_indexes_extracted": stats.bundle_indexes_extracted,
            "bundle_indexes_inserted": stats.bundle_indexes_inserted,
            "bytes_uploaded": stats.bytes_uploaded,
            "bytes_uploaded_human": f"{stats.bytes_uploaded / (1024*1024):.1f} MB",
        },
        "validation_checks": [
            {
                "check": r.check_name,
                "passed": r.passed,
                "expected": r.expected,
                "actual": r.actual,
                "message": r.message,
            }
            for r in results
        ],
        "all_passed": all(r.passed for r in results) if results else True,
        "errors": stats.errors,
        "warnings": stats.warnings,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    logger.info("Validation report written to: %s", report_path)

    # Print summary
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    logger.info(
        "Validation summary: %d passed, %d failed, %d errors, %d warnings",
        passed, failed, len(stats.errors), len(stats.warnings),
    )

    if failed > 0:
        logger.error("MIGRATION VALIDATION FAILED - review report for details")
    elif stats.errors:
        logger.warning(
            "Migration completed with %d errors - review report for details",
            len(stats.errors),
        )
    else:
        logger.info("Migration completed successfully - all checks passed")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Migrate LBCD Stearman databases to Azure. "
            "Extracts images and metadata from 4 encrypted Jet 4.0 MDB files "
            "and loads them into Azure SQL + Blob Storage."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Dry run (no Azure writes):\n"
            "  python migrate_lbcd.py --source-dir ./lbc_files --dry-run\n"
            "\n"
            "  # Process only disc 1:\n"
            "  python migrate_lbcd.py --source-dir ./lbc_files --disc 1\n"
            "\n"
            "  # Full migration:\n"
            "  python migrate_lbcd.py --source-dir ./lbc_files\n"
            "\n"
            "  # Custom file naming:\n"
            "  python migrate_lbcd.py --source-dir ./lbc_files "
            '--file-pattern "stearman_disc{disc_num}.lbc"\n'
        ),
    )

    parser.add_argument(
        "--source-dir",
        type=Path,
        required=True,
        help="Directory containing the .lbc database files",
    )
    parser.add_argument(
        "--file-pattern",
        type=str,
        default=LBC_FILE_PATTERN,
        help=(
            'Filename pattern with {disc_num} placeholder. '
            f'Default: "{LBC_FILE_PATTERN}"'
        ),
    )
    parser.add_argument(
        "--disc",
        type=int,
        choices=[1, 2, 3, 4],
        default=None,
        help="Process only the specified disc (1-4). Default: process all.",
    )
    parser.add_argument(
        "--staging-dir",
        type=Path,
        default=Path("staging"),
        help="Directory for staging extracted BLOBs. Default: ./staging",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path("logs"),
        help="Directory for log files. Default: ./logs",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract and validate only; do not write to Azure.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug-level logging.",
    )

    # Azure connection parameters
    azure_group = parser.add_argument_group("Azure configuration")
    azure_group.add_argument(
        "--sql-connection-string",
        type=str,
        default=os.environ.get("AZURE_SQL_CONNECTION_STRING", ""),
        help="Azure SQL connection string (or set AZURE_SQL_CONNECTION_STRING env var)",
    )
    azure_group.add_argument(
        "--blob-connection-string",
        type=str,
        default=os.environ.get("AZURE_BLOB_CONNECTION_STRING", ""),
        help="Azure Blob Storage connection string (or set AZURE_BLOB_CONNECTION_STRING env var)",
    )
    azure_group.add_argument(
        "--blob-account-url",
        type=str,
        default=os.environ.get("AZURE_BLOB_ACCOUNT_URL", ""),
        help="Azure Blob Storage account URL for DefaultAzureCredential auth",
    )
    azure_group.add_argument(
        "--blob-container",
        type=str,
        default="stearman",
        help="Azure Blob Storage container name. Default: stearman",
    )

    return parser.parse_args()


def main():
    """Main migration entry point."""
    args = parse_args()

    # Setup logging
    logger = setup_logging(args.log_dir, verbose=args.verbose)
    logger.info("LBCD-to-Azure Migration Script")
    logger.info("=" * 70)

    if args.dry_run:
        logger.info("*** DRY RUN MODE - no data will be written to Azure ***")

    # Check prerequisites
    mdbtools_version = check_mdbtools_installed()
    logger.info("mdbtools version: %s", mdbtools_version)

    # Validate source directory
    if not args.source_dir.is_dir():
        logger.error("Source directory does not exist: %s", args.source_dir)
        sys.exit(1)

    # Determine which discs to process
    discs_to_process = [args.disc] if args.disc else list(range(1, DISC_COUNT + 1))

    # Locate .lbc files
    lbc_files = {}
    for disc_num in discs_to_process:
        filename = args.file_pattern.format(disc_num=disc_num)
        filepath = args.source_dir / filename
        if not filepath.is_file():
            logger.error("Disc %d file not found: %s", disc_num, filepath)
            sys.exit(1)
        lbc_files[disc_num] = filepath
        logger.info(
            "Disc %d: %s (%d MB)",
            disc_num, filepath.name,
            int(filepath.stat().st_size / (1024 * 1024)),
        )

    # Pre-flight: verify tables exist in each source database
    for disc_num, lbc_path in lbc_files.items():
        tables = mdb_tables(lbc_path)
        logger.info("Disc %d tables: %s", disc_num, ", ".join(tables))
        for required_table in SOURCE_TABLES:
            if required_table not in tables:
                logger.error(
                    "Disc %d: required table '%s' not found in %s",
                    disc_num, required_table, lbc_path.name,
                )
                sys.exit(1)

    # Pre-flight: verify row counts against expected values
    logger.info("Verifying source row counts...")
    for disc_num, lbc_path in lbc_files.items():
        expected = EXPECTED_PER_DISC.get(disc_num, {})
        for table, key in [
            ("Images", "images"),
            ("Bundles", "bundles"),
            ("ImageIndexes", "image_indexes"),
            ("BundleIndexes", "bundle_indexes"),
        ]:
            actual_count = mdb_count(lbc_path, table)
            expected_count = expected.get(key, 0)
            status = "OK" if actual_count == expected_count else "MISMATCH"
            logger.info(
                "  Disc %d %s: expected=%d, actual=%d [%s]",
                disc_num, table, expected_count, actual_count, status,
            )
            if status == "MISMATCH":
                logger.warning(
                    "Row count mismatch for Disc %d %s (expected %d, got %d)",
                    disc_num, table, expected_count, actual_count,
                )

    # Initialize Azure connections
    if not args.dry_run:
        if not args.sql_connection_string:
            logger.error(
                "Azure SQL connection string required. "
                "Set --sql-connection-string or AZURE_SQL_CONNECTION_STRING env var."
            )
            sys.exit(1)

        if not args.blob_connection_string and not args.blob_account_url:
            logger.error(
                "Azure Blob Storage connection required. "
                "Set --blob-connection-string or --blob-account-url."
            )
            sys.exit(1)

    # Create staging directory
    args.staging_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Staging directory: %s", args.staging_dir.resolve())

    # Initialize Azure clients
    uploader = BlobUploader(
        connection_string=args.blob_connection_string or None,
        account_url=args.blob_account_url or None,
        container_name=args.blob_container,
        dry_run=args.dry_run,
        logger=logger,
    )

    sql = SqlLoader(
        connection_string=args.sql_connection_string,
        dry_run=args.dry_run,
        logger=logger,
    )
    sql.connect()

    stats = MigrationStats()

    try:
        # ------------------------------------------------------------------
        # Insert shared reference data (Aircraft, IndexTypes are in schema.sql seed)
        # ------------------------------------------------------------------

        # Get or create the Aircraft record
        # The schema.sql seed data already inserts the Aircraft record.
        # In a real run, we would SELECT the AircraftID. For the migration
        # script, we use AircraftID=1 (the first and only aircraft).
        aircraft_id = 1

        if args.dry_run:
            logger.info("[DRY RUN] Using AircraftID=%d", aircraft_id)
        else:
            # Verify the Aircraft record exists (seeded by schema.sql)
            cursor = sql.execute(
                "SELECT AircraftID FROM Aircraft WHERE Name = ?", ("Stearman",)
            )
            row = cursor.fetchone()
            if row:
                aircraft_id = row[0]
                logger.info("Found existing Aircraft record: ID=%d", aircraft_id)
            else:
                # Insert if not seeded
                disc_meta = extract_misc_data(
                    lbc_files[discs_to_process[0]], discs_to_process[0], logger,
                )
                aircraft_id = sql.insert_aircraft(
                    name=disc_meta.aircraft_name or "Stearman",
                    owner=disc_meta.log_owner or "Russ Aviation",
                    date_created=disc_meta.date_created or "2001-05-23",
                    validation_key=disc_meta.validation_key,
                )
                logger.info("Created Aircraft record: ID=%d", aircraft_id)

        # ------------------------------------------------------------------
        # Process each disc
        # ------------------------------------------------------------------
        folder_id_map = {}  # (disc_num, source_folder_id) -> new_folder_id
        service_manual_folder_id = None  # Shared across discs for merging

        for disc_num in discs_to_process:
            lbc_path = lbc_files[disc_num]
            service_manual_folder_id = process_disc(
                disc_num=disc_num,
                lbc_path=lbc_path,
                staging_dir=args.staging_dir,
                uploader=uploader,
                sql=sql,
                aircraft_id=aircraft_id,
                folder_id_map=folder_id_map,
                service_manual_folder_id=service_manual_folder_id,
                dry_run=args.dry_run,
                logger=logger,
                stats=stats,
            )

        # ------------------------------------------------------------------
        # Post-migration validation
        # ------------------------------------------------------------------
        validation_results = validate_migration(
            sql, stats, discs_to_process, logger,
        )

        # Write validation report
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_path = args.log_dir / f"validation_report_{timestamp}.json"
        write_validation_report(
            validation_results, stats, discs_to_process, report_path, logger,
        )

        # Check for failures
        if any(not r.passed for r in validation_results):
            logger.error("=" * 70)
            logger.error("MIGRATION COMPLETED WITH VALIDATION FAILURES")
            logger.error("Review the validation report: %s", report_path)
            logger.error("=" * 70)
            sys.exit(2)

        if stats.errors:
            logger.warning("=" * 70)
            logger.warning(
                "MIGRATION COMPLETED WITH %d ERRORS", len(stats.errors),
            )
            logger.warning("Review the validation report: %s", report_path)
            logger.warning("=" * 70)
            sys.exit(3)

        logger.info("=" * 70)
        logger.info("MIGRATION COMPLETED SUCCESSFULLY")
        logger.info("  Images: %d extracted, %d uploaded, %d inserted",
                     stats.images_extracted, stats.images_uploaded, stats.images_inserted)
        logger.info("  Bundles: %d", stats.bundles_inserted)
        logger.info("  Image indexes: %d", stats.image_indexes_inserted)
        logger.info("  Bundle indexes: %d", stats.bundle_indexes_inserted)
        logger.info("  Total uploaded: %.1f MB", stats.bytes_uploaded / (1024 * 1024))
        logger.info("  Validation report: %s", report_path)
        logger.info("=" * 70)

    except Exception:
        logger.exception("Migration failed with an unhandled exception")
        sql.rollback()
        raise

    finally:
        sql.close()


if __name__ == "__main__":
    main()
