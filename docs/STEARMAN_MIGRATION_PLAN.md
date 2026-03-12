# Stearman Parts Database — Migration Plan

**Project:** LBCD Stearman Aircraft Logbook → Modern Web Application  
**Client:** Russ Aviation / Russ Aircraft  
**Prepared by:** RedEye Network Solutions  
**Date:** March 12, 2026  
**Version:** 1.0

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Source Data Architecture Analysis](#2-source-data-architecture-analysis)
3. [Target Architecture](#3-target-architecture)
4. [Data Migration Strategy](#4-data-migration-strategy)
5. [Feature Parity Matrix](#5-feature-parity-matrix)
6. [New Features](#6-new-features)
7. [Azure Infrastructure](#7-azure-infrastructure)
8. [Implementation Phases](#8-implementation-phases)
9. [Risk Assessment](#9-risk-assessment)
10. [Appendices](#10-appendices)

---

## 1. Executive Summary

### Background

Russ Aviation owns a 4-disc set of digitized Stearman aircraft engineering drawings and service manuals, created by AirLog Imaging in May 2001 using their "LogBooksOnCD" (LBCD) software. The data is stored in **4 encrypted Microsoft Jet 4.0 (Access MDB) databases** totaling ~1.9 GB, containing **7,673 scanned images** with **19,828 searchable index records**.

The LBCD desktop viewer software hasn't been updated since 2001 and is incompatible with modern operating systems. The databases are password-protected (Jet 4.0 RC4 encryption), making them inaccessible without specialized tools.

### Objective

Migrate all images, metadata, and search functionality to a modern, cloud-hosted web application that:
- Preserves 100% of the original data with full fidelity
- Provides equivalent or better search and navigation capabilities
- Adds multi-user access, mobile support, and modern search
- Can serve as a **reusable platform** for other LBCD database owners in the aviation industry

### Scope

| Metric | Value |
|--------|-------|
| Database files | 4 (Jet 4.0 MDB, encrypted) |
| Total database size | 1,878 MB |
| Total images | 7,673 |
| Total bundles (multi-page groups) | 396 |
| Total search index records | 19,828 |
| Image format | TIFF (Group 4 compressed, B&W, ~12000×9000px) + JPEG thumbnails |
| Index types | Drawing # and Key Word |
| Folder categories | Frame Drawings (A–N), Service Manual |
| Created | May 23–24, 2001 |
| Owner | Russ Aviation / Russ Aircraft |

---

## 2. Source Data Architecture Analysis

### 2.1 Database Schema

All 4 disc databases share an **identical schema** with 8 tables:

#### `Images` — Primary image storage
| Column | Type | Description |
|--------|------|-------------|
| `ImageID` | Long Integer (PK) | Auto-increment, per-disc |
| `Image` | OLE/BLOB | Full-resolution TIFF image data |
| `Thumbnail` | OLE/BLOB | 106×106 JPEG thumbnail |
| `FolderID` | Long Integer (FK) | Parent folder reference |
| `ImagePosition` | Long Integer | Display order within folder |
| `FileName` | Text(50) | Original filename, e.g. `A FRAME DRAWINGS(001).tif` |
| `BundleID` | Long Integer (FK) | Bundle group (0 = standalone) |
| `BundleOffset` | Long Integer | Position within bundle (1-based) |
| `Notes` | Memo | User annotations (currently unused across all discs) |

**Image format details:**
- Full images: TIFF, little-endian, Group 4 (CCITT fax) compression, 1-bit B&W
- Typical resolution: 12,845 × 8,871 pixels (~E-size engineering drawings at 200 DPI)
- Average size: ~250 KB per image (range: 50 KB – 500+ KB)
- Thumbnails: JPEG, 106×106 pixels, grayscale, ~1.5 KB each
- 1 JPEG cover image per disc; remainder are TIFF

#### `Bundles` — Multi-page document groups
| Column | Type | Description |
|--------|------|-------------|
| `BundleID` | Long Integer (PK) | Auto-increment |
| `FolderID` | Long Integer (FK) | Parent folder |
| `ImagePosition` | Long Integer | Bundle's position in folder view |
| `Notes` | Memo | Bundle-level notes (unused) |

Bundles group related images (e.g., multi-sheet drawings, assembly sets). Images in a bundle share the same `ImagePosition` but differ by `BundleOffset` (1, 2, 3…). Filenames use dot notation: `M FRAME DRAWINGS(017.001).tif`, `M FRAME DRAWINGS(017.002).tif`.

#### `ImageIndexes` — Per-image search metadata
| Column | Type | Description |
|--------|------|-------------|
| `ImageIndexID` | Long Integer (PK) | Auto-increment |
| `ImageID` | Long Integer (FK) | References Images |
| `IndexTypeID` | Long Integer (FK) | References IndexTypes |
| `IndexString` | Text(40) | The searchable value |

Each image has **multiple index records** — typically one Drawing # and one or more Key Words. Example:
- Image 1 → Drawing # `73-1000`, Key Word `BLOCK`, Key Word `STANDARD TITLE`

#### `BundleIndexes` — Per-bundle search metadata
| Column | Type | Description |
|--------|------|-------------|
| `BundleIndexID` | Long Integer (PK) | Auto-increment |
| `BundleID` | Long Integer (FK) | References Bundles |
| `IndexTypeID` | Long Integer (FK) | References IndexTypes |
| `IndexString` | Text(40) | The searchable value |

Same structure as ImageIndexes but applied to bundles. When a bundle has indexes, all images in that bundle share those index values.

#### `Folders` — Hierarchical folder structure
| Column | Type | Description |
|--------|------|-------------|
| `FolderID` | Long Integer (PK) | Auto-increment, per-disc |
| `ParentFolderID` | Long Integer | Parent (0 = root) |
| `FolderName` | Text(255) | Display name |
| `Notes` | Memo | Folder-level notes (unused) |

Simple 2-level hierarchy: Root → Category folders.

#### `FolderIndexes` — Per-folder search metadata
Same schema as ImageIndexes/BundleIndexes but for folders. **Empty across all 4 discs.**

#### `IndexTypes` — Search field definitions
| Column | Type | Description |
|--------|------|-------------|
| `IndexTypeID` | Long Integer (PK) | 1 or 2 |
| `Index` | Text(50) | Display name |
| `IndexCode` | Text(5) | Short code |

Only 2 index types across all discs:
| ID | Name | Code |
|----|------|------|
| 1 | Drawing # | DG |
| 2 | Key Word | KW |

#### `MiscData` — Database metadata
| Column | Type | Description |
|--------|------|-------------|
| `KeyWord` | Text(50) | Key |
| `String` | Text(255) | Value |

Contains per-disc metadata:
| Key | Value |
|-----|-------|
| AirCraft | Stearman |
| DateCreated | 05/23/2001 or 05/24/2001 |
| LogOwner | Russ Aviation / Russ Aircraft |
| ValidationKey | B4F93241-9C86-11d4-AEA6-0000863547E9 |
| Version | 1.0 |

### 2.2 Per-Disc Inventory

| Disc | Root Folder | Sub-Folders | Images | Bundles | Image Indexes | Bundle Indexes | DB Size |
|------|-------------|-------------|--------|---------|---------------|----------------|---------|
| 1 | DISC_1_STEARMAN | `SERVICE MANUAL, A–E FRAME DRAWINGS | 2,889 | 2 | 8,248 | 3 | 529 MB |
| 2 | DISC_2_STEARMAN | `SERVICE MANUAL, F–H FRAME DRAWINGS | 1,778 | 4 | 4,863 | 9 | 449 MB |
| 3 | DISC_3_STEARMAN | `SERVICE MANUAL, J–L FRAME DRAWINGS | 1,783 | 132 | 3,990 | 371 | 528 MB |
| 4 | DISC_4_STEARMAN | `SERVICE MANUAL, M–N FRAME DRAWINGS | 1,223 | 258 | 1,595 | 749 | 372 MB |
| **Total** | | **17 unique folders** | **7,673** | **396** | **18,696** | **1,132** | **1,878 MB** |

### 2.3 Content Description

This is a **complete set of Stearman biplane engineering drawings and service manual pages**:
- **Frame Drawings (A through N):** Engineering/manufacturing drawings organized alphabetically by Stearman's frame designation system. These are large-format technical drawings showing parts, assemblies, and details.
- **Service Manual:** Maintenance and service documentation pages, duplicated (or continued) across each disc.
- **Drawing Numbers:** Boeing-Stearman part/drawing numbers (e.g., `73-1000`, `75-2366`, `E75-3118`, `120-24189`)
- **Keywords:** Describe the part or assembly shown (e.g., `COWL ASSY.`, `WING SPAR`, `LANDING GEAR`, `FUSELAGE SIDE PANEL`)

### 2.4 Entity Relationship Diagram

```
MiscData (standalone key-value config)

IndexTypes ─────────────────────────────────┐
  │                                          │
  ├──→ ImageIndexes.IndexTypeID              │
  ├──→ BundleIndexes.IndexTypeID             │
  └──→ FolderIndexes.IndexTypeID             │
                                             │
Folders ─────────────────────────────────────┤
  │  (self-referencing: ParentFolderID)      │
  ├──→ Images.FolderID                       │
  ├──→ Bundles.FolderID                      │
  └──→ FolderIndexes.FolderID               │
                                             │
Images ──────────────────────────────────────┤
  ├──→ ImageIndexes.ImageID                  │
  └──→ Bundles.BundleID (via Images.BundleID)│
                                             │
Bundles ─────────────────────────────────────┘
  └──→ BundleIndexes.BundleID
```

---

## 3. Target Architecture

### 3.1 Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                    Azure Cloud                            │
│                                                          │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────┐ │
│  │   Azure      │    │  Azure App   │    │   Azure     │ │
│  │   Static     │◄──►│  Service /   │◄──►│   SQL DB    │ │
│  │   Web Apps   │    │  Container   │    │  (Serverless)│ │
│  │  (React SPA) │    │  App (API)   │    │             │ │
│  └─────────────┘    └──────┬───────┘    └─────────────┘ │
│                            │                             │
│                     ┌──────┴───────┐                     │
│                     │   Azure      │                     │
│                     │   Blob       │                     │
│                     │   Storage    │                     │
│                     │  (Images)    │                     │
│                     └──────┬───────┘                     │
│                            │                             │
│                     ┌──────┴───────┐                     │
│                     │   Azure AI   │                     │
│                     │   Search     │                     │
│                     │              │                     │
│                     └──────────────┘                     │
│                                                          │
│  ┌──────────────┐   ┌──────────────┐                     │
│  │  Azure CDN   │   │  Entra ID    │                     │
│  │ (image cache)│   │  (auth)      │                     │
│  └──────────────┘   └──────────────┘                     │
└──────────────────────────────────────────────────────────┘
```

### 3.2 Technology Decisions

#### Database: **Azure SQL Database (Serverless)** ✅

**Recommended over Cosmos DB** because:
- Source data is **highly relational** — images belong to folders, bundles group images, indexes reference images/bundles/folders via foreign keys
- Query patterns are primarily **search and filter** (by drawing #, keyword, folder), not document lookups
- Data volume is modest (~20K metadata records) — no need for Cosmos DB's horizontal scale
- Azure SQL Serverless auto-pauses when idle → minimal cost for low-traffic periods
- Familiar SQL for RedEye's team; simpler to debug and maintain

**Estimated size:** < 100 MB for all metadata (images stored in Blob Storage)

#### Frontend: **React + TypeScript SPA**

- Hosted on Azure Static Web Apps (free tier for basic usage)
- OpenSeadragon or similar for deep-zoom TIFF viewing
- Responsive design for mobile/tablet
- Tree navigation component for folder hierarchy

#### Backend: **Python FastAPI**

- Hosted on Azure Container Apps (or App Service)
- Clean REST API for metadata queries, image serving, search
- Python ecosystem for future OCR integration (Tesseract, Azure AI Vision)
- FastAPI auto-generates OpenAPI docs

#### Image Storage: **Azure Blob Storage (Hot tier)**

- TIFFs converted to multi-resolution tiles (DZI format) for web viewing
- Original TIFFs preserved in archive tier for regulatory compliance
- Thumbnails served directly
- Azure CDN in front for global performance

#### Search: **Azure AI Search**

- Full-text search across Drawing #, Keywords, Notes, OCR text
- Faceted navigation (filter by folder, drawing number prefix, keyword)
- Fuzzy matching for typos in part numbers
- Suggester for type-ahead autocomplete

#### Authentication: **Microsoft Entra ID (B2C)**

- Supports individual accounts (email/password) and social login
- Scalable if offered as a multi-tenant SaaS product
- Fine-grained access control per database/aircraft

### 3.3 Target Database Schema (Azure SQL)

```sql
-- Unified schema merging all 4 discs

CREATE TABLE Aircraft (
    AircraftID INT IDENTITY PRIMARY KEY,
    Name NVARCHAR(100) NOT NULL,          -- 'Stearman'
    Owner NVARCHAR(255),                   -- 'Russ Aviation'
    DateCreated DATE,                      -- Original LBCD creation date
    SourceValidationKey NVARCHAR(100),     -- Original ValidationKey
    CreatedAt DATETIME2 DEFAULT GETUTCDATE()
);

CREATE TABLE Folders (
    FolderID INT IDENTITY PRIMARY KEY,
    AircraftID INT NOT NULL REFERENCES Aircraft(AircraftID),
    ParentFolderID INT NULL REFERENCES Folders(FolderID),
    SourceDiscNumber INT NOT NULL,         -- 1-4 (provenance tracking)
    SourceFolderID INT NOT NULL,           -- Original FolderID in source disc
    FolderName NVARCHAR(255) NOT NULL,
    SortOrder INT DEFAULT 0,
    Notes NVARCHAR(MAX),
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    UNIQUE (AircraftID, SourceDiscNumber, SourceFolderID)
);

CREATE TABLE Images (
    ImageID INT IDENTITY PRIMARY KEY,
    FolderID INT NOT NULL REFERENCES Folders(FolderID),
    BundleID INT NULL,                     -- NULL = standalone
    BundleOffset INT NULL,                 -- Position within bundle
    ImagePosition INT NOT NULL,            -- Display order in folder
    OriginalFileName NVARCHAR(255),
    BlobPath NVARCHAR(500) NOT NULL,       -- Azure Blob Storage path (full TIFF)
    TilePath NVARCHAR(500),                -- DZI tile path for web viewing
    ThumbnailPath NVARCHAR(500),           -- Thumbnail blob path
    ImageWidth INT,
    ImageHeight INT,
    FileSizeBytes BIGINT,
    MimeType NVARCHAR(50) DEFAULT 'image/tiff',
    OcrText NVARCHAR(MAX),                 -- Future: OCR extracted text
    Notes NVARCHAR(MAX),
    SourceDiscNumber INT NOT NULL,
    SourceImageID INT NOT NULL,
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    ModifiedAt DATETIME2,
    UNIQUE (SourceDiscNumber, SourceImageID)
);

CREATE TABLE Bundles (
    BundleID INT IDENTITY PRIMARY KEY,
    FolderID INT NOT NULL REFERENCES Folders(FolderID),
    ImagePosition INT NOT NULL,
    Notes NVARCHAR(MAX),
    SourceDiscNumber INT NOT NULL,
    SourceBundleID INT NOT NULL,
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    UNIQUE (SourceDiscNumber, SourceBundleID)
);

-- Add FK after both tables exist
ALTER TABLE Images ADD CONSTRAINT FK_Images_Bundles
    FOREIGN KEY (BundleID) REFERENCES Bundles(BundleID);

CREATE TABLE IndexTypes (
    IndexTypeID INT IDENTITY PRIMARY KEY,
    Name NVARCHAR(50) NOT NULL,            -- 'Drawing #', 'Key Word'
    Code NVARCHAR(10) NOT NULL,            -- 'DG', 'KW'
    UNIQUE (Code)
);

CREATE TABLE ImageIndexes (
    ImageIndexID INT IDENTITY PRIMARY KEY,
    ImageID INT NOT NULL REFERENCES Images(ImageID),
    IndexTypeID INT NOT NULL REFERENCES IndexTypes(IndexTypeID),
    IndexValue NVARCHAR(100) NOT NULL,     -- Expanded from 40 chars
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    INDEX IX_ImageIndexes_Value NONCLUSTERED (IndexValue),
    INDEX IX_ImageIndexes_TypeValue NONCLUSTERED (IndexTypeID, IndexValue)
);

CREATE TABLE BundleIndexes (
    BundleIndexID INT IDENTITY PRIMARY KEY,
    BundleID INT NOT NULL REFERENCES Bundles(BundleID),
    IndexTypeID INT NOT NULL REFERENCES IndexTypes(IndexTypeID),
    IndexValue NVARCHAR(100) NOT NULL,
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    INDEX IX_BundleIndexes_Value NONCLUSTERED (IndexValue)
);

-- Audit trail
CREATE TABLE AuditLog (
    AuditID BIGINT IDENTITY PRIMARY KEY,
    UserID NVARCHAR(128),
    Action NVARCHAR(50),                   -- 'VIEW', 'SEARCH', 'EXPORT', 'NOTE_EDIT'
    EntityType NVARCHAR(50),               -- 'Image', 'Bundle', 'Folder'
    EntityID INT,
    Details NVARCHAR(MAX),
    Timestamp DATETIME2 DEFAULT GETUTCDATE()
);

-- Full-text catalog for notes and OCR
CREATE FULLTEXT CATALOG StearmanFT;
CREATE FULLTEXT INDEX ON Images(Notes, OcrText) KEY INDEX PK__Images ON StearmanFT;
```

---

## 4. Data Migration Strategy

### 4.1 Overview

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐
│  4 × MDB    │────►│  Extract &   │────►│  Transform   │────►│  Load to    │
│  (Jet 4.0)  │     │  Stage       │     │  & Convert   │     │  Azure      │
└─────────────┘     └──────────────┘     └──────────────┘     └─────────────┘
                     mdbtools on          TIFF → DZI tiles     Blob Storage
                     Linux                Merge 4 discs        Azure SQL
                                          Validate integrity   AI Search index
```

### 4.2 Phase 1: Extract & Stage

**Tool:** `mdbtools` on Linux (confirmed working with these encrypted databases)

```bash
# For each disc:
mdb-export -b hex disc${N}.lbc Images    # Extract images with hex-encoded blobs
mdb-export disc${N}.lbc Folders          # CSV export of metadata tables
mdb-export disc${N}.lbc Bundles
mdb-export disc${N}.lbc ImageIndexes
mdb-export disc${N}.lbc BundleIndexes
mdb-export disc${N}.lbc IndexTypes
mdb-export disc${N}.lbc MiscData
```

**Image extraction pipeline (Python):**
1. Parse CSV export with hex-encoded blobs
2. Decode hex → binary for each Image and Thumbnail
3. Write to staging directory: `staging/disc{N}/images/{ImageID}.tif`
4. Write thumbnails: `staging/disc{N}/thumbs/{ImageID}.jpg`
5. Record SHA-256 hash of each file for integrity verification

**Estimated staging storage:** ~2 GB (images) + ~12 MB (thumbnails)

### 4.3 Phase 2: Merge 4 Discs

The 4 discs are **separate volumes of a single dataset**, split across CDs due to 2001 media constraints. They should be merged into a **unified database**.

**Merging strategy:**
1. Create a single `Aircraft` record for "Stearman"
2. Merge folder hierarchies:
   - Combine the 4 root folders (DISC_1–4_STEARMAN) under one root
   - Merge duplicate "`SERVICE MANUAL`" folders into one (appears on all 4 discs)
   - Keep Frame Drawing folders separate (A through N) — they're already unique
3. Re-map all IDs:
   - Source IDs are per-disc (Image 1 exists in all 4 discs)
   - New unified IDs via IDENTITY columns
   - Preserve source disc # and source ID for traceability
4. Verify no data loss: row counts must match source

**Merged folder structure:**
```
📁 STEARMAN (root)
  📁 SERVICE MANUAL (merged from all 4 discs)
  📁 A FRAME DRAWINGS (Disc 1)
  📁 B FRAME DRAWINGS (Disc 1)
  📁 C FRAME DRAWINGS (Disc 1)
  📁 D FRAME DRAWINGS (Disc 1)
  📁 E FRAME DRAWINGS (Disc 1)
  📁 F FRAME DRAWINGS (Disc 2)
  📁 G FRAME DRAWINGS (Disc 2)
  📁 H FRAME DRAWINGS (Disc 2)
  📁 J FRAME DRAWINGS (Disc 3)
  📁 K FRAME DRAWINGS (Disc 3)
  📁 L FRAME DRAWINGS (Disc 3)
  📁 M FRAME DRAWINGS (Disc 4)
  📁 N FRAME DRAWINGS (Disc 4)
```

Note: Frame letters skip "I" (aviation convention to avoid confusion with numeral "1").

### 4.4 Phase 3: Image Processing

For each extracted TIFF:

1. **Validate TIFF integrity** — verify headers, check for corruption
2. **Generate web-optimized versions:**
   - **DZI (Deep Zoom Image) tiles** for OpenSeadragon viewer — pre-tiled pyramidal format for smooth pan/zoom of 12000×9000px images
   - **Medium-resolution JPEG** (2000px wide) for quick preview
   - **Thumbnail JPEG** (200×200) — upgrade from source 106×106
3. **Preserve originals** — upload unmodified TIFFs to Azure Blob Storage archive tier
4. **Extract TIFF metadata** — width, height, DPI, compression type

**Estimated output:**
| Format | Count | Avg Size | Total |
|--------|-------|----------|-------|
| Original TIFF (archive) | 7,673 | 250 KB | ~1.9 GB |
| DZI tiles (web viewing) | 7,673 | ~500 KB | ~3.8 GB |
| Medium JPEG | 7,673 | ~100 KB | ~750 MB |
| Thumbnail JPEG | 7,673 | ~5 KB | ~38 MB |
| **Total** | | | **~6.5 GB** |

### 4.5 Phase 4: Load to Azure

1. **Upload images to Blob Storage:**
   ```
   stearman/
     originals/disc{N}/{ImageID}.tif
     tiles/{ImageID}/              (DZI directory)
     previews/{ImageID}.jpg
     thumbnails/{ImageID}.jpg
   ```

2. **Load metadata to Azure SQL:**
   - Insert Aircraft, IndexTypes first
   - Insert merged Folders
   - Insert Bundles with new IDs
   - Insert Images with blob paths and new BundleID references
   - Insert ImageIndexes and BundleIndexes with re-mapped IDs

3. **Build Azure AI Search index:**
   - Index all ImageIndexes and BundleIndexes
   - Include folder names, filenames, notes
   - Configure suggester on IndexValue field

### 4.6 Data Validation & Integrity

| Check | Method |
|-------|--------|
| Image count | Source count (7,673) = Blob Storage count = SQL count |
| Image integrity | SHA-256 of extracted TIFF matches re-read from Blob |
| Index count | Source total (19,828) = SQL total |
| Bundle integrity | All bundle members present; offsets contiguous |
| Folder hierarchy | All images reference valid folders |
| Search completeness | Every image/bundle in source has all its index records |
| Visual spot-check | Random sample of 50 images viewed in web app vs source |

### 4.7 Handling Multi-Page Bundles

Bundles are groups of images that represent a single logical document:
- In the source, images share an `ImagePosition` but have different `BundleOffset` values
- In the web app, bundles will be displayed as:
  - A **carousel/gallery** within the folder view
  - Page indicators showing "Page 1 of 3"
  - Combined search results (searching a bundle index hits all pages)
- Bundle-level indexes apply to all images in the bundle
- Individual images in a bundle may also have their own indexes

---

## 5. Feature Parity Matrix

| # | LBCD Feature | Web App Equivalent | Notes |
|---|-------------|-------------------|-------|
| 1 | Tree navigation (folder hierarchy) | React tree component with expand/collapse | Enhanced with breadcrumbs and URL routing |
| 2 | Thumbnail grid view | Responsive image grid with lazy loading | Larger thumbnails (200px vs 106px) |
| 3 | Full-resolution image viewing | OpenSeadragon deep-zoom viewer | Smooth pan/zoom on 12K×9K images |
| 4 | Image zoom (1:1, fit-to-window) | Continuous zoom, pinch-to-zoom on mobile | Superior to LBCD's fixed zoom levels |
| 5 | Keyword search | Azure AI Search with facets | Faster, fuzzy matching, autocomplete |
| 6 | Drawing # search | Dedicated search field with prefix matching | Type-ahead suggestions |
| 7 | List of Values (master index) | Browsable/filterable index page | Sortable, paginated, exportable |
| 8 | Properties display per image | Side panel / overlay with all metadata | Drawing #s, keywords, folder, bundle info |
| 9 | Notes (view/add/edit) | Rich text notes editor per image | Multi-user, timestamped, audit trail |
| 10 | Image export | Download original TIFF or converted JPEG/PNG | Batch export support |
| 11 | Print functionality | Browser print + PDF export | Full-page, scaled, or contact sheet |
| 12 | Multi-page bundles | Carousel with page indicators | Swipe navigation on mobile |
| 13 | Database password protection | Entra ID authentication | Role-based access, SSO |
| 14 | CD-based distribution | URL-based access, anywhere | No installation required |

---

## 6. New Features

### 6.1 Multi-User Concurrent Access
- Multiple users can browse, search, and annotate simultaneously
- No file locking or single-user limitations
- User-specific notes and bookmarks

### 6.2 Mobile & Tablet Support
- Responsive design works on any screen size
- Touch-optimized: pinch-to-zoom, swipe between pages
- Progressive Web App (PWA) for offline thumbnail browsing

### 6.3 Advanced Search
- **Full-text search** across all fields simultaneously
- **Faceted filtering:** by folder, drawing number range, keyword
- **Fuzzy matching:** finds `COWL ASSY` when you type `cowl assembly`
- **Search suggestions:** type-ahead autocomplete
- **Saved searches:** bookmark frequently used queries

### 6.4 OCR on Scanned Images
- Azure AI Vision or Tesseract OCR on all 7,673 images
- Extracts text from the engineering drawings themselves
- Makes handwritten annotations, title blocks, and revision notes searchable
- Dramatically improves searchability beyond the original 2-field index

### 6.5 PDF Export
- Export single images, bundles, folders, or entire categories as PDF
- Maintains original resolution
- Includes metadata cover page
- Useful for FAA inspections, insurance, and documentation packages

### 6.6 Audit Trail
- Full history of who viewed, searched, exported, or annotated
- Regulatory compliance for aviation records
- Exportable audit reports

### 6.7 Sharing & Collaboration
- Share individual images or folders via secure links
- Time-limited access tokens for external parties (mechanics, inspectors)
- Comments/annotations on specific images

### 6.8 Cross-Reference & Related Parts
- Automatically link images that share the same Drawing # or Keywords
- "Related drawings" panel showing associated parts/assemblies
- Visual relationship graph of interconnected parts

### 6.9 Comparison View
- Side-by-side comparison of two drawings
- Useful for comparing revisions or related parts
- Overlay mode for spotting differences

### 6.10 API Access
- REST API for programmatic access
- Enables integration with maintenance management systems
- Webhook support for automated workflows

---

## 7. Azure Infrastructure

### 7.1 Resource Group Layout

```
rg-stearman-prod
├── Azure SQL Database (Serverless, General Purpose)
├── Azure Blob Storage (LRS, Hot + Archive tiers)
├── Azure Container App (API backend)
├── Azure Static Web App (React frontend)
├── Azure AI Search (Free or Basic tier)
├── Azure CDN (Microsoft standard)
├── Azure Key Vault (secrets)
├── Azure Application Insights (monitoring)
└── Azure Log Analytics Workspace
```

### 7.2 Infrastructure as Code (Bicep)

```bicep
// main.bicep - Core infrastructure
targetScope = 'resourceGroup'

param location string = 'westus2'
param environment string = 'prod'
param projectName string = 'stearman'

// Azure SQL Database - Serverless
resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: '${projectName}-${environment}-sql'
  location: location
  properties: {
    administratorLogin: 'stearmanadmin'
    administratorLoginPassword: '<from-keyvault>'
    minimalTlsVersion: '1.2'
  }
}

resource sqlDatabase 'Microsoft.Sql/servers/databases@2023-08-01-preview' = {
  parent: sqlServer
  name: '${projectName}db'
  location: location
  sku: {
    name: 'GP_S_Gen5_1'      // Serverless, 1 vCore
    tier: 'GeneralPurpose'
    family: 'Gen5'
    capacity: 1
  }
  properties: {
    autoPauseDelay: 60        // Pause after 1 hour idle
    minCapacity: '0.5'        // Min 0.5 vCores
    maxSizeBytes: 1073741824  // 1 GB
  }
}

// Storage Account
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: '${projectName}${environment}storage'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

// Container App for API
resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${projectName}-${environment}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
    }
  }
}

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${projectName}-${environment}-api'
  location: location
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
      }
    }
    template: {
      containers: [
        {
          name: 'api'
          image: '${projectName}acr.azurecr.io/api:latest'
          resources: {
            cpu: '0.25'
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3
      }
    }
  }
}

// Azure AI Search
resource search 'Microsoft.Search/searchServices@2024-03-01-preview' = {
  name: '${projectName}-${environment}-search'
  location: location
  sku: { name: 'basic' }    // Basic tier: 15M docs, 2GB storage
  properties: {
    replicaCount: 1
    partitionCount: 1
  }
}
```

### 7.3 Estimated Monthly Cost

| Resource | SKU | Estimated Cost/Month | Notes |
|----------|-----|---------------------|-------|
| Azure SQL (Serverless) | GP_S_Gen5_1 | $5 – $30 | Auto-pauses when idle; pay per-second |
| Blob Storage (Hot, 7GB) | Standard LRS | $1.50 | ~7 GB tiles + previews + originals |
| Blob Storage (Archive, 2GB) | Standard LRS | $0.04 | Original TIFFs for compliance |
| Container App (API) | 0.25 vCPU, 0.5GB | $0 – $15 | Scale to zero; free allocation |
| Static Web App (Frontend) | Free tier | $0 | Includes SSL, CDN, CI/CD |
| Azure AI Search | Basic | $75 | Smallest paid tier; Free tier has 50MB limit |
| Azure CDN | Standard Microsoft | $1 – $5 | Minimal traffic expected |
| Key Vault | Standard | $0.50 | Secrets storage |
| Application Insights | Pay-as-you-go | $0 – $2 | 5 GB/month free |
| **Total (low usage)** | | **~$85 – $130/month** | |
| **Total (moderate usage)** | | **~$130 – $200/month** | |

**Cost optimization opportunities:**
- Start with Azure AI Search **Free tier** (50 MB, 3 indexes) during development — sufficient for 20K index records
- Use Container App consumption plan (first 180K vCPU-sec/month free)
- SQL Serverless auto-pause saves money during nights/weekends
- If this is offered as a SaaS product, costs scale linearly with customers

---

## 8. Implementation Phases

### Phase 0: Foundation (Week 1–2)
- [ ] Set up Azure resource group and infrastructure (Bicep deploy)
- [ ] Set up Git repository and CI/CD pipelines
- [ ] Create development environment
- [ ] Define API contracts (OpenAPI spec)

### Phase 1: Data Migration (Week 2–4)
- [ ] Write Python extraction script (mdbtools → staging)
- [ ] Extract all 7,673 images from all 4 discs
- [ ] Validate extracted images (count, SHA-256, TIFF integrity)
- [ ] Generate DZI tiles for web viewing
- [ ] Upload to Azure Blob Storage
- [ ] Load metadata into Azure SQL
- [ ] Run validation suite (counts, referential integrity)
- [ ] Build Azure AI Search index

**Deliverable:** All data in Azure, fully validated, searchable

### Phase 2: Core Web Application (Week 4–8)
- [ ] Backend API: folder listing, image metadata, image serving, search
- [ ] Frontend: folder tree navigation, thumbnail grid, image viewer (OpenSeadragon)
- [ ] Frontend: search interface with facets and suggestions
- [ ] Frontend: image detail view (properties, indexes, notes)
- [ ] Authentication: Entra ID integration
- [ ] Bundle/multi-page support

**Deliverable:** Functional web app with feature parity to LBCD viewer

### Phase 3: Enhanced Features (Week 8–12)
- [ ] Notes editing with audit trail
- [ ] PDF export (single image, bundle, folder)
- [ ] Image download (original TIFF, converted JPEG/PNG)
- [ ] Advanced search (fuzzy, type-ahead, saved searches)
- [ ] Related drawings panel
- [ ] Mobile/tablet optimization

**Deliverable:** Production-ready web app with enhanced features

### Phase 4: Intelligence & Polish (Week 12–16)
- [ ] OCR processing of all images (Azure AI Vision)
- [ ] Full-text search including OCR text
- [ ] Comparison view
- [ ] Print layout optimization
- [ ] Performance optimization and load testing
- [ ] Security audit
- [ ] User documentation

**Deliverable:** Fully featured, polished application

### Phase 5: Multi-Tenant / SaaS (Future)
- [ ] Multi-tenant architecture (multiple aircraft/owners)
- [ ] Self-service database upload (user uploads their .lbc files)
- [ ] Automated LBCD import pipeline
- [ ] Subscription/billing integration
- [ ] Marketing site

**Deliverable:** SaaS product for aviation industry

---

## 9. Risk Assessment

### 9.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Image corruption during extraction** | Low | High | SHA-256 checksums at every stage; visual spot-check sample; keep source files untouched |
| **TIFF format incompatibility** | Low | Medium | Group 4 TIFF is a well-supported standard; test with multiple viewers |
| **mdbtools extraction errors** | Low | Medium | Cross-validate record counts; already confirmed working on all 4 discs |
| **Large TIFF rendering performance** | Medium | Medium | DZI tiling + CDN solves this; test on low-bandwidth connections |
| **Service Manual deduplication** | Medium | Low | May have duplicate pages across discs; need to compare and deduplicate or keep all with provenance |
| **Azure AI Search cost if scaling** | Low | Medium | Start with Free tier; Basic tier sufficient for foreseeable scale |
| **Data loss during ID remapping** | Low | High | Preserve source disc # and original IDs; full audit trail; reversible migration |

### 9.2 Regulatory / Compliance Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **FAA record authenticity** | Medium | High | Preserve original TIFFs bit-for-bit in archive tier; SHA-256 chain of custody; audit log |
| **Data sovereignty** | Low | Medium | Keep all data in US Azure regions; document data residency |
| **Access control for sensitive records** | Medium | Medium | Entra ID authentication; role-based access; no anonymous access |
| **Audit trail requirements** | Medium | High | Full AuditLog table; who viewed/exported/modified what and when |

**Important note:** These are **engineering drawings** (not airworthiness certificates or maintenance logbooks in the FAA 14 CFR Part 43 sense), so the regulatory burden is lower than for primary maintenance records. However, they may be referenced during type certificate data sheet (TCDS) reviews or Supplemental Type Certificate (STC) applications, so maintaining provenance and authenticity is still important.

### 9.3 Business Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Low user adoption** | Medium | Medium | Simple, intuitive UI; no training needed; mobile support |
| **Ongoing Azure costs with no revenue** | Medium | Medium | Serverless/auto-pause architecture minimizes idle costs; ~$85/month floor |
| **SaaS market too small** | Medium | High | Validate demand before investing in multi-tenant; start as a service offering |
| **Competition from digitization vendors** | Low | Low | LBCD is a niche legacy format; RedEye's offering is data liberation, not scanning |

### 9.4 Data Preservation Strategy

Given the irreplaceable nature of this data:

1. **Source files:** Keep all 4 original .lbc files in cold storage (Azure Archive Blob + local backup)
2. **Extracted TIFFs:** Archive tier in Blob Storage + local backup
3. **Database backups:** Azure SQL automated backups (35-day retention) + monthly export to Blob
4. **Migration audit:** Complete log of every record extracted, transformed, and loaded
5. **Checksum manifest:** SHA-256 of every image at every stage, stored alongside the data

---

## 10. Appendices

### Appendix A: Source Database Access

**Connection method:** `mdbtools` on Linux (Ubuntu 24.04)

```bash
# List tables
mdb-tables -1 disc1.lbc

# Export table to CSV
mdb-export disc1.lbc Folders

# Export with hex-encoded blobs
mdb-export -b hex disc1.lbc Images

# Get row count
mdb-count disc1.lbc Images

# Get schema (DDL)
mdb-schema disc1.lbc
```

The Jet 4.0 "encryption" is weak XOR masking that mdbtools handles transparently. The database password `SPINER` is needed for Access ODBC/OLEDB but not for mdbtools.

**Alternative access on Windows:** Install Microsoft Access Database Engine 2016 (64-bit) and use pyodbc:
```python
import pyodbc
conn = pyodbc.connect(
    r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};'
    r'DBQ=C:\path\to\disc1.lbc;'
    r'PWD=SPINER;'
)
```

### Appendix B: Image Format Details

| Property | Value |
|----------|-------|
| Format | TIFF (Tagged Image File Format) |
| Byte order | Little-endian (II) |
| Compression | CCITT Group 4 (T.6) bi-level |
| Color | 1-bit black and white |
| Typical width | 12,000 – 13,000 pixels |
| Typical height | 8,000 – 9,000 pixels |
| Effective DPI | ~200 DPI (E-size drawing, 34" × 22") |
| Average file size | ~250 KB |

### Appendix C: LBCD Software Background

- **Product:** LogBooksOnCD (LBCD)
- **Company:** AirLog Imaging (no longer operational)
- **Version:** 1.0 (May 2001)
- **Platform:** Windows 95/98/NT/2000
- **Format:** Microsoft Jet 4.0 MDB with custom .lbc extension
- **Encryption:** Jet 4.0 database password (`SPINER`)
- **Validation:** UUID-based license key per database set
- **Distribution:** 4 CDs per aircraft set (limited by CD capacity)

### Appendix D: Unique Index Values Summary

| Disc | Unique Drawing #s | Unique Keywords |
|------|-------------------|-----------------|
| 1 | ~2,718 | ~2,487 |
| 2 | ~1,600 | ~1,500 |
| 3 | ~1,200 | ~1,200 |
| 4 | ~800 | ~800 |
| **Est. Total (deduplicated)** | **~5,000 – 6,000** | **~4,500 – 5,500** |

Drawing number prefixes observed: `70-xxxx`, `73-xxxx`, `75-xxxx`, `120-xxxxx`, `E75-xxxx` (Boeing-Stearman engineering numbering system).

### Appendix E: Multi-Tenant SaaS Considerations

If RedEye offers this as a service to other LBCD database owners:

1. **Automated import pipeline:** Upload .lbc file → auto-detect schema → extract → deploy
2. **Per-tenant isolation:** Separate Blob containers, SQL schemas or databases
3. **Pricing model:** Per-database monthly fee ($50–$200/month) or per-user
4. **Target market:** Aviation museums, vintage aircraft restorers, maintenance shops with legacy LBCD data
5. **Marketing angle:** "Your 20-year-old aviation records, accessible from any device"
6. **Legal:** Ensure clients own the data rights (LBCD license may have terms)

---

*Document prepared by RedEye Network Solutions. For questions, contact Brian at RedEye Network Solutions.*
