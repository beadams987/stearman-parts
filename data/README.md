# Stearman Parts — Source Data Archive

This directory contains the original source databases and all extracted content
from the Boeing-Stearman aircraft engineering drawings collection.

**All large files (`.lbc`, `.tif`, `.jpg`) are stored via Git LFS.**

---

## Directory Structure

```
data/
├── source/                        # Original LBCD source databases
│   ├── disc1.lbc  (529 MB)        # AirLog LogBooksOnCD Disc 1 of 4
│   ├── disc2.lbc  (450 MB)        # AirLog LogBooksOnCD Disc 2 of 4
│   ├── disc3.lbc  (528 MB)        # AirLog LogBooksOnCD Disc 3 of 4
│   └── disc4.lbc  (372 MB)        # AirLog LogBooksOnCD Disc 4 of 4
│
└── extracted/                     # Extracted image content
    ├── disc1/
    │   ├── images/  (2,889 TIFFs) # Full-resolution drawings (~12000×9000px)
    │   └── thumbs/  (2,889 JPEGs) # 106×106px JPEG thumbnails
    ├── disc2/
    │   ├── images/  (1,778 TIFFs)
    │   └── thumbs/  (1,778 JPEGs)
    ├── disc3/
    │   ├── images/  (1,783 TIFFs)
    │   └── thumbs/  (1,783 JPEGs)
    └── disc4/
        ├── images/  (1,223 TIFFs)
        └── thumbs/  (1,223 JPEGs)
```

**Totals:** 7,673 images · 7,673 thumbnails · 4 source databases · ~3.8 GB

---

## Source Format

- **Format:** Microsoft Jet 4.0 / Access MDB (`.lbc` extension, AirLog proprietary)
- **Product:** AirLog Imaging LogBooksOnCD v1.0 (May 2001)
- **Aircraft:** Boeing-Stearman (Russ Aviation collection)
- **Images:** CCITT Group 4 TIFF, 1-bit B&W, typically 5,500–13,162 × 5,000–8,999 px
- **Extraction tool:** mdbtools v1.0.0

---

## Extraction

Images were extracted from the encrypted Jet 4.0 MDB files using `mdbtools`
and the migration script at `scripts/migrate_lbcd.py`. See `EXTRACTION_STATUS.md`
for full details.

To re-extract from source:
```bash
python3 scripts/migrate_lbcd.py --source-dir data/source --staging-dir data/extracted --dry-run
```
