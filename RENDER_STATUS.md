# RENDER_STATUS.md

Pre-rendered JPEG pipeline — completed **2026-03-13 04:02 UTC**

## Summary

| Metric | Value |
|--------|-------|
| Total images processed | 7,673 |
| Conversion errors | 0 |
| Upload errors | 0 |
| DB rows updated | 7,673 |
| Total JPEG size | **11.42 GB** |
| Conversion time | ~23 min (8-core parallel) |
| Azure upload time | ~13 min (16-thread) |
| LFS push time | ~33 min (11 MB/s) |
| Total elapsed | ~42 min (conversion+upload), +33 min LFS |

## What Was Done

### 1. Azure Blob Storage — `renders` container

- Created `renders` container in `ststearmanimages` storage account
- Bulk converted all 7,673 Group-4 compressed 1-bit TIFF engineering drawings to JPEG
  - Quality: 90
  - Max width: 4,000px (preserves detail for large drawings up to 13,162 × 8,999px)
  - Mode: RGB (1-bit → RGB via Pillow)
  - Blob path: `disc{N}/{OriginalFileName_stem}.jpg`
    e.g. `disc4/M FRAME DRAWINGS(115).jpg`

**Container stats (confirmed):** 7,673 blobs · 11.42 GB

### 2. Database — `stearmandb`

- Added `RenderPath NVARCHAR(500) NULL` column to `Images` table
- Populated all 7,673 rows with the pre-rendered blob path
- Sample: `ImageID=100001 → disc1/\`SERVICE MANUAL(001).jpg`

```sql
ALTER TABLE Images ADD RenderPath NVARCHAR(500) NULL;
-- All 7,673 rows populated
```

### 3. API — `api/`

**`app/services/blob_service.py`**
- Added `get_render_url(blob_path)` method — generates 1-hour SAS URL for
  the `renders` container (same mechanism as `get_thumbnail_url`)

**`app/routers/images.py`**
- `GET /api/images/{id}` now fetches `RenderPath` column
- `render_url` in `ImageDetailResponse`:
  - If `RenderPath` is set → SAS-signed URL from `renders` container
  - Fallback → `/api/images/{id}/render` (live TIFF→JPEG conversion endpoint)
- Added `_get_renders_blob_service(settings)` helper

**`app/routers/search.py`**
- Search results `thumbnail_url` now returns SAS-signed URLs
  (was returning raw relative paths like `disc1/thumb_1.jpg`)
- Added `_get_thumbs_blob_service(settings)` helper
- Handles both SQL fallback and Azure AI Search paths

**`app/config.py`**
- `BLOB_THUMBS_CONTAINER_NAME = "thumbnails"` (was `"thumbs"`)
- `BLOB_RENDERS_CONTAINER_NAME = "renders"` (new)

### 4. GitHub — `beadams987/stearman-parts`

**Commits pushed:**
```
c4199e45  data: add 7,673 pre-rendered JPEGs via Git LFS
2e8d67f6  feat: pre-rendered JPEG pipeline for browser-inline viewing
```

**LFS objects:** 23,023 total (was 15,350 — added 7,673 render JPEGs)

```
.gitattributes addition:
  data/rendered/**/*.jpg filter=lfs diff=lfs merge=lfs -text
```

Files in repo: `data/rendered/disc{1-4}/*.jpg` (7,673 files, 11.42 GB via LFS)

## ⚠️ Notes

### GitHub LFS Storage

Pushing 11.42 GB to GitHub LFS exceeds the default free tier (1 GB storage).
GitHub may require paid LFS storage data packs ($5/month per 50 GB storage + 50 GB bandwidth).
The push **succeeded** — verify billing settings in the repo at
https://github.com/beadams987/stearman-parts/settings/billing

### Pillow Decompression Warnings

Several very large drawings (>89 MP) triggered `DecompressionBombWarning` from Pillow.
These are warnings only — all files converted successfully. To silence:
```python
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # add to convert script
```

### Fallback Endpoint

The `/api/images/{id}/render` endpoint still exists and works as a live fallback.
It now activates only when `RenderPath IS NULL` (which should never happen
for the current corpus, but protects against future ingestion before rendering).

## Disc Breakdown

| Disc | Images | Source TIFFs | Rendered JPEGs |
|------|--------|-------------|----------------|
| disc1 | 2,889 | 2,888 TIFFs + 1 JPEG source | 2,889 JPEGs |
| disc2 | 1,778 | 1,778 TIFFs | 1,778 JPEGs |
| disc3 | 1,783 | 1,783 TIFFs | 1,783 JPEGs |
| disc4 | 1,223 | 1,223 TIFFs | 1,223 JPEGs |
| **Total** | **7,673** | | **7,673 JPEGs** |

## Failure Log

`/tmp/stearman-renders/failures.json` — empty (zero failures)
