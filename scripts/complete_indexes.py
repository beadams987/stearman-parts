#!/usr/bin/env python3
"""
Complete missing ImageIndexes for discs 2, 3, 4.
Disc 1 indexes are complete. Disc 2 is partial. Disc 3 and 4 are empty.
"""

import csv
import io
import subprocess
import sys
from pathlib import Path

import pyodbc

LBC_DIR = Path("/tmp/stearman-parts/lbc_files")
CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=stearman-dbsrv.database.windows.net;"
    "DATABASE=stearmandb;"
    "UID=stearmanadmin;"
    "PWD=StearmanMigrate2026!;"
    "Encrypt=yes;"
    "TrustServerCertificate=no"
)

csv.field_size_limit(sys.maxsize)


def mdb_export(lbc_path: Path, table: str) -> list[dict]:
    result = subprocess.run(
        ["mdb-export", str(lbc_path), table],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"mdb-export failed: {result.stderr}")
    reader = csv.DictReader(io.StringIO(result.stdout))
    return list(reader)


def complete_indexes_for_disc(conn, disc_num: int):
    lbc_path = LBC_DIR / f"disc{disc_num}.lbc"
    cursor = conn.cursor()

    # Get set of ImageIDs that already have at least one index
    cursor.execute(
        "SELECT DISTINCT ImageID FROM ImageIndexes WHERE ImageID BETWEEN ? AND ?",
        (disc_num * 100000 + 1, disc_num * 100000 + 99999),
    )
    already_indexed = {row[0] for row in cursor.fetchall()}
    print(f"Disc {disc_num}: {len(already_indexed)} images already indexed")

    # Get all images for this disc to know valid source IDs
    cursor.execute(
        "SELECT SourceImageID, ImageID FROM Images WHERE SourceDiscNumber = ?",
        (disc_num,),
    )
    source_to_new = {row[0]: row[1] for row in cursor.fetchall()}
    print(f"Disc {disc_num}: {len(source_to_new)} total images in DB")

    # Extract ImageIndexes from source
    print(f"Disc {disc_num}: extracting ImageIndexes from {lbc_path.name}...")
    rows = mdb_export(lbc_path, "ImageIndexes")
    print(f"Disc {disc_num}: {len(rows)} index records in source")

    # Insert missing ones in batches
    inserted = 0
    skipped_already = 0
    skipped_unmapped = 0

    batch_size = 1000
    batch = []

    for row in rows:
        src_image_id = int(row["ImageID"])
        new_image_id = source_to_new.get(src_image_id)
        if new_image_id is None:
            skipped_unmapped += 1
            continue

        if new_image_id in already_indexed:
            skipped_already += 1
            continue

        index_type_id = int(row["IndexTypeID"])
        index_value = row.get("IndexString", "").strip()
        if not index_value:
            continue

        batch.append((new_image_id, index_type_id, index_value))

        if len(batch) >= batch_size:
            cursor.executemany(
                "INSERT INTO ImageIndexes (ImageID, IndexTypeID, IndexValue) VALUES (?, ?, ?)",
                batch,
            )
            inserted += len(batch)
            batch = []
            if inserted % 5000 == 0:
                conn.commit()
                print(f"  Disc {disc_num}: {inserted} indexes inserted...")

    if batch:
        cursor.executemany(
            "INSERT INTO ImageIndexes (ImageID, IndexTypeID, IndexValue) VALUES (?, ?, ?)",
            batch,
        )
        inserted += len(batch)

    conn.commit()
    print(f"Disc {disc_num}: done — inserted={inserted}, "
          f"skipped_already_indexed={skipped_already}, "
          f"skipped_unmapped={skipped_unmapped}")
    return inserted


def main():
    conn = pyodbc.connect(CONN_STR, autocommit=False)

    total_inserted = 0
    for disc_num in [2, 3, 4]:
        print(f"\n{'='*60}")
        print(f"Processing disc {disc_num}...")
        print(f"{'='*60}")
        inserted = complete_indexes_for_disc(conn, disc_num)
        total_inserted += inserted

    # Final counts
    cursor = conn.cursor()
    for disc_num in range(1, 5):
        cursor.execute(
            """
            SELECT COUNT(ix.ImageIndexID)
            FROM ImageIndexes ix
            INNER JOIN Images i ON i.ImageID = ix.ImageID
            WHERE i.SourceDiscNumber = ?
            """,
            (disc_num,),
        )
        count = cursor.fetchone()[0]
        print(f"Disc {disc_num}: {count} image indexes in DB")

    cursor.execute("SELECT COUNT(*) FROM ImageIndexes")
    total = cursor.fetchone()[0]
    print(f"\nTotal ImageIndexes: {total} (expected 18,696)")
    print(f"Total new indexes inserted: {total_inserted}")

    conn.close()


if __name__ == "__main__":
    main()
