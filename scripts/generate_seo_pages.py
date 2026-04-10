#!/usr/bin/env python3
"""Generate static SEO content pages for search engine indexing.

Creates lightweight HTML files in web/public/seo/ that search engines can crawl.
Each page contains manual titles, descriptions, keywords, and OCR text excerpts
that are invisible to SPA users (they get the React app) but visible to crawlers.

These files are served by Azure Static Web Apps alongside the SPA.

Usage:
    python generate_seo_pages.py

Environment variables:
    AZURE_SQL_CONNECTION_STRING
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pyodbc

# Add parent dir to import catalog
sys.path.insert(0, str(Path(__file__).parent.parent / "api" / "app"))
from catalog import ALL_ITEMS, CATEGORIES


OUTPUT_DIR = Path(__file__).parent.parent / "web" / "public" / "seo"
SITE_URL = os.environ.get("SITE_BASE_URL", "https://stearmanhq.com")


def get_db():
    return pyodbc.connect(os.environ["AZURE_SQL_CONNECTION_STRING"], autocommit=True)


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def generate_manuals_index():
    """Generate a static HTML page listing all manuals with descriptions."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    items_html = ""
    for item in ALL_ITEMS:
        models_str = ", ".join(item.models) if item.models else ""
        tags_str = ", ".join(item.tags) if item.tags else ""
        items_html += f"""
        <article>
            <h3>{escape_html(item.title)}</h3>
            <p>{escape_html(item.description)}</p>
            <p><strong>Category:</strong> {escape_html(item.category)}</p>
            {f'<p><strong>Aircraft Models:</strong> {escape_html(models_str)}</p>' if models_str else ''}
            {f'<p><strong>Tags:</strong> {escape_html(tags_str)}</p>' if tags_str else ''}
            <p><strong>Source:</strong> {escape_html(item.source)}</p>
            <p><a href="{SITE_URL}/manuals">View in Manuals Library</a></p>
        </article>
        <hr>
        """

    categories_html = "".join(f"<li>{escape_html(c)}</li>" for c in CATEGORIES)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Boeing-Stearman Kaydet Technical Manuals Library — Complete Reference</title>
    <meta name="description" content="Complete library of {len(ALL_ITEMS)} Boeing-Stearman Kaydet technical documents: maintenance manuals, parts catalogs, pilot handbooks, training materials, engine overhaul instructions, FAA regulatory data, and NTSB safety reports for PT-13, PT-17, PT-18, N2S series aircraft.">
    <meta name="keywords" content="Stearman, Kaydet, Boeing-Stearman, PT-13, PT-17, N2S, manuals, parts catalog, pilot handbook, service instructions, overhaul, Continental R-670, engineering drawings, biplane, restoration">
    <link rel="canonical" href="{SITE_URL}/seo/manuals.html">
    <meta name="robots" content="index, follow">
</head>
<body>
    <h1>Boeing-Stearman Kaydet Technical Manuals Library</h1>
    <p>The definitive collection of {len(ALL_ITEMS)} technical documents for Boeing-Stearman Model 75 (Kaydet) aircraft, including the PT-13, PT-13B, PT-13D, PT-17, PT-18, PT-27, N2S-1, N2S-2, N2S-3, N2S-4, and N2S-5 variants.</p>

    <h2>Categories</h2>
    <ul>{categories_html}</ul>

    <h2>All Documents</h2>
    {items_html}

    <footer>
        <p><a href="{SITE_URL}">Return to Stearman Information Hub</a></p>
        <p>Public domain documents sourced from U.S. Government publications, stearman-aero.com, FAA, NTSB, Internet Archive, and community contributors.</p>
    </footer>
</body>
</html>"""

    path = OUTPUT_DIR / "manuals.html"
    path.write_text(html)
    print(f"Generated: {path} ({len(ALL_ITEMS)} items)")


def generate_drawings_index():
    """Generate a static HTML page listing drawing categories with AI descriptions."""
    conn = get_db()
    cursor = conn.cursor()

    # Get folder structure
    cursor.execute("""
        SELECT f.FolderID, f.FolderName, f.ParentFolderID,
               (SELECT COUNT(*) FROM Images i WHERE i.FolderID = f.FolderID) as ImageCount
        FROM Folders f ORDER BY f.SortOrder, f.FolderName
    """)
    folders = cursor.fetchall()

    # Get sample AI descriptions
    cursor.execute("""
        SELECT TOP 50 i.ImageID, f.FolderName, i.OriginalFileName, 
               LEFT(i.AiDescription, 500) as Description
        FROM Images i
        JOIN Folders f ON i.FolderID = f.FolderID
        WHERE i.AiDescription IS NOT NULL AND i.AiDescription != ''
        ORDER BY NEWID()
    """)
    samples = cursor.fetchall()

    folders_html = ""
    for f in folders:
        if f.ImageCount > 0:
            folders_html += f"<li><strong>{escape_html(f.FolderName)}</strong> — {f.ImageCount} engineering drawings</li>\n"

    samples_html = ""
    for s in samples:
        desc = escape_html(s.Description or "")
        samples_html += f"""
        <article>
            <h3>{escape_html(s.OriginalFileName or f'Drawing {s.ImageID}')}</h3>
            <p><strong>Category:</strong> {escape_html(s.FolderName)}</p>
            <p>{desc}</p>
            <p><a href="{SITE_URL}/images/{s.ImageID}">View Drawing</a></p>
        </article>
        """

    total_images = sum(f.ImageCount for f in folders)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Boeing-Stearman Kaydet Engineering Drawings Archive — {total_images:,} Drawings</title>
    <meta name="description" content="Searchable archive of {total_images:,} Boeing-Stearman Kaydet engineering drawings and frame diagrams. Covers frame drawings A through N plus service manual illustrations for PT-13, PT-17, N2S series biplanes.">
    <meta name="keywords" content="Stearman engineering drawings, Boeing-Stearman blueprints, Kaydet drawings, frame drawings, biplane parts diagrams, PT-17 drawings, N2S drawings, aircraft engineering">
    <link rel="canonical" href="{SITE_URL}/seo/drawings.html">
    <meta name="robots" content="index, follow">
</head>
<body>
    <h1>Boeing-Stearman Kaydet Engineering Drawings Archive</h1>
    <p>Complete searchable archive of {total_images:,} digitized Boeing-Stearman engineering drawings, originally created by the Stearman Aircraft Company in Wichita, Kansas. These drawings cover every frame designation (A through N) plus service manual illustrations.</p>

    <h2>Drawing Categories</h2>
    <ul>{folders_html}</ul>

    <h2>Sample Drawings (AI-Analyzed)</h2>
    <p>Each drawing has been analyzed by AI to identify parts, assemblies, drawing numbers, and readable text.</p>
    {samples_html}

    <footer>
        <p><a href="{SITE_URL}">Return to Stearman Information Hub</a></p>
        <p>Original engineering drawings from the Russ Aviation Collection, digitized by AirLog Imaging (2001).</p>
    </footer>
</body>
</html>"""

    path = OUTPUT_DIR / "drawings.html"
    path.write_text(html)
    print(f"Generated: {path} ({total_images} images, {len(samples)} AI descriptions)")
    conn.close()


def update_sitemap():
    """Add SEO pages to the sitemap."""
    sitemap_path = Path(__file__).parent.parent / "web" / "public" / "sitemap.xml"
    if sitemap_path.exists():
        content = sitemap_path.read_text()
        seo_entries = f"""
  <url>
    <loc>{SITE_URL}/seo/manuals.html</loc>
    <changefreq>weekly</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>{SITE_URL}/seo/drawings.html</loc>
    <changefreq>weekly</changefreq>
    <priority>0.9</priority>
  </url>"""
        if "/seo/manuals.html" not in content:
            content = content.replace("</urlset>", f"{seo_entries}\n</urlset>")
            sitemap_path.write_text(content)
            print(f"Updated sitemap with SEO pages")


if __name__ == "__main__":
    generate_manuals_index()
    generate_drawings_index()
    update_sitemap()
    print("SEO pages generated!")
