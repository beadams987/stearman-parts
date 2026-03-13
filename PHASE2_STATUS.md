# Phase 2 Migration Status

**Date:** 2026-03-12  
**Status:** ✅ COMPLETE (with notes)

---

## Azure SQL — Database Schema

**Status:** ✅ Schema already deployed (from prior partial migration)

Tables confirmed present:
- `Aircraft`, `Discs`, `Folders`, `Bundles`, `Images`, `ImageIndexes`, `BundleIndexes`
- `IndexTypes`, `AccessTiers`, `SearchCache`

---

## Azure SQL — Data Load

**Status:** ✅ Complete

| Table | Count | Expected | Status |
|-------|-------|----------|--------|
| Images | 7,673 | 7,673 | ✅ |
| Bundles | 396 | 396 | ✅ |
| BundleIndexes | 1,132 | 1,132 | ✅ |
| ImageIndexes | 18,694 | 18,696 | ⚠️ -2 |

**Notes on ImageIndexes (18,694 vs 18,696):**  
2 records had empty `IndexString` values in the source `.lbc` databases and were intentionally skipped.  
All other index records are loaded. Disc-by-disc breakdown:

| Disc | Indexes | Source |
|------|---------|--------|
| 1 | 8,248 | disc1.lbc |
| 2 | 4,861 | disc2.lbc |
| 3 | 3,990 | disc3.lbc |
| 4 | 1,595 | disc4.lbc |
| **Total** | **18,694** | |

**Completion note:** A prior migration run had loaded discs 1 and partial disc 2 (2,752 indexes).  
Phase 2 completed disc 2 and loaded discs 3 and 4 via `scripts/complete_indexes.py`.

---

## Azure Blob Storage

**Status:** ✅ Complete (loaded by prior migration)

| Container | Count | Notes |
|-----------|-------|-------|
| `images` | 7,673 | Full-resolution TIFFs |
| `thumbnails` | 7,673 | 106×106 JPEG thumbnails |

**Blob path format in DB:**  
- Images: `disc{N}/{image_name}.tif` (in `images` container)  
- Thumbs: `disc{N}/thumb_{id}.jpg` (in `thumbnails` container)

> Note: Blob paths use separate `images`/`thumbnails` containers rather than the `stearman` container
> referenced in the migration script. Function App config updated to match actual structure.

---

## GitHub Secret — SWA Deployment Token

**Status:** ✅ Set

```
Secret: SWA_DEPLOYMENT_TOKEN
Repo: beadams987/stearman-parts
```

---

## Function App Configuration

**Status:** ✅ Applied

Settings applied to `func-stearman-api`:

| Setting | Value |
|---------|-------|
| `AZURE_SQL_CONNECTION_STRING` | `DRIVER={ODBC Driver 18...}SERVER=stearman-dbsrv...` |
| `AZURE_BLOB_CONNECTION_STRING` | `DefaultEndpointsProtocol=https;AccountName=ststearmanimages...` |
| `BLOB_CONTAINER_NAME` | `images` |
| `BLOB_THUMBS_CONTAINER_NAME` | `thumbnails` |

---

## Git LFS Archival

**Status:** ✅ Committed / 🔄 Push in progress

Commits added to `beadams987/stearman-parts`:

| Commit | Contents | LFS Objects |
|--------|----------|-------------|
| `96ef5b4` | LFS tracking setup, .gitattributes, data/README.md | — |
| `ca86628` | `data/source/` — 4 × .lbc files | 4 |
| `f58ed43` | `data/extracted/disc1/` | 5,778 |
| `8943881` | `data/extracted/disc2/` | 3,556 |
| `c501209` | `data/extracted/disc3/` | 3,566 |
| `0120fe9` | `data/extracted/disc4/` | 2,446 |

**Total LFS objects:** ~15,350 (4 .lbc + 7,673 TIFFs + 7,673 JPEGs)  
**Estimated LFS storage:** ~3.8 GB

**LFS tracking rules** (in `.gitattributes`):
```
data/source/*.lbc filter=lfs diff=lfs merge=lfs -text
data/extracted/**/*.tif filter=lfs diff=lfs merge=lfs -text
data/extracted/**/*.tiff filter=lfs diff=lfs merge=lfs -text
data/extracted/**/*.jpg filter=lfs diff=lfs merge=lfs -text
```

> ⚠️ **GitHub LFS Storage Note:** This push requires ~3.8GB of LFS storage.
> GitHub free tier includes 1GB LFS storage. You will likely need a Git LFS
> Data Pack ($5/month for 50GB) at: https://github.com/settings/billing

---

## Issues & Deviations

1. **Prior partial migration:** Phases 1+2 had been partially run before this execution.
   All data was already in Blob storage; SQL had images/bundles/bundle-indexes complete
   but only 11,000/18,696 image indexes. Phase 2 completed the missing indexes.

2. **Blob container names:** Source used `images`/`thumbnails` containers, not the
   `stearman` single container the migration script anticipated. Function App config
   was updated to match the actual deployed structure.

3. **ImageIndexes -2:** Two source records had empty `IndexString` in disc2.lbc.
   These are genuinely empty in the source data.

---

## Summary

All primary migration goals achieved:
- ✅ 7,673 images in Azure SQL + Blob Storage
- ✅ 396 bundles with 1,132 bundle indexes
- ✅ 18,694/18,696 image indexes (99.99%)
- ✅ Function App configured
- ✅ SWA deployment token set as GitHub secret
- ✅ Full source data + extracted images committed to GitHub with LFS
