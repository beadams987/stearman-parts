#!/usr/bin/env python3
"""Generate sitemap.xml for thekaydet.com from Azure SQL data.

Outputs to web/public/sitemap.xml for inclusion in the SWA build.

Usage:
    python generate_sitemap.py                    # Generate sitemap
    python generate_sitemap.py --output /path/to  # Custom output dir

Environment variables:
    AZURE_SQL_CONNECTION_STRING
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent

import pyodbc

BASE_URL = "https://thekaydet.com"
TODAY = datetime.now(UTC).strftime("%Y-%m-%d")


def get_db_connection() -> pyodbc.Connection:
    conn_str = os.environ["AZURE_SQL_CONNECTION_STRING"]
    return pyodbc.connect(conn_str, autocommit=True)


def generate_sitemap(output_dir: Path) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()

    urlset = Element("urlset")
    urlset.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")

    def add_url(loc: str, changefreq: str = "monthly", priority: str = "0.5") -> None:
        url_el = SubElement(urlset, "url")
        SubElement(url_el, "loc").text = loc
        SubElement(url_el, "lastmod").text = TODAY
        SubElement(url_el, "changefreq").text = changefreq
        SubElement(url_el, "priority").text = priority

    # Static pages
    add_url(f"{BASE_URL}/", changefreq="weekly", priority="1.0")
    add_url(f"{BASE_URL}/search", changefreq="weekly", priority="0.8")
    add_url(f"{BASE_URL}/manuals", changefreq="monthly", priority="0.8")

    # Folders
    cursor.execute("SELECT FolderID FROM Folders ORDER BY FolderID")
    folders = cursor.fetchall()
    for row in folders:
        add_url(f"{BASE_URL}/folders/{row.FolderID}", changefreq="monthly", priority="0.7")

    # Images (the most valuable pages for SEO)
    cursor.execute("SELECT ImageID FROM Images ORDER BY ImageID")
    images = cursor.fetchall()
    for row in images:
        add_url(f"{BASE_URL}/images/{row.ImageID}", changefreq="yearly", priority="0.6")

    # Bundles
    cursor.execute("SELECT BundleID FROM Bundles ORDER BY BundleID")
    bundles = cursor.fetchall()
    for row in bundles:
        add_url(f"{BASE_URL}/bundles/{row.BundleID}", changefreq="yearly", priority="0.5")

    conn.close()

    # Write sitemap
    tree = ElementTree(urlset)
    indent(tree, space="  ")
    output_path = output_dir / "sitemap.xml"
    tree.write(output_path, xml_declaration=True, encoding="UTF-8")

    total = 3 + len(folders) + len(images) + len(bundles)
    print(f"Sitemap generated: {output_path}")
    print(f"  Static pages: 3")
    print(f"  Folders: {len(folders)}")
    print(f"  Images: {len(images)}")
    print(f"  Bundles: {len(bundles)}")
    print(f"  Total URLs: {total}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate sitemap.xml")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent.parent / "web" / "public",
        help="Output directory (default: web/public/)",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    generate_sitemap(args.output)


if __name__ == "__main__":
    main()
