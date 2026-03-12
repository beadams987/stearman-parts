-- =============================================================================
-- Stearman Parts Database Schema
-- Target: Azure SQL Database (Serverless, General Purpose)
-- =============================================================================
--
-- Unified schema for Boeing-Stearman aircraft engineering drawings migrated
-- from 4 encrypted LBCD (Jet 4.0 MDB) databases.
--
-- Source: AirLog Imaging LogBooksOnCD v1.0 (May 2001)
-- Images: 7,673 scanned TIFF drawings (Group 4, ~12000x9000px)
-- Indexes: 19,828 searchable records (Drawing # and Key Word)
--
-- Image BLOBs are stored in Azure Blob Storage, NOT in this database.
-- This schema holds metadata, search indexes, user accounts, and audit logs.
--
-- Created: 2026-03-12
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Access tiers (free/paid/admin)
-- Must be created before Users due to FK dependency.
-- ---------------------------------------------------------------------------
CREATE TABLE AccessTiers (
    AccessTierID INT IDENTITY(1,1) PRIMARY KEY,
    Name NVARCHAR(50) NOT NULL,              -- 'free', 'paid', 'admin'
    Description NVARCHAR(255),
    MaxImagesPerDay INT,                     -- NULL = unlimited
    CanDownloadOriginals BIT DEFAULT 1,
    CanExportPDF BIT DEFAULT 1,
    CreatedAt DATETIME2 DEFAULT GETUTCDATE()
);

-- ---------------------------------------------------------------------------
-- Aircraft metadata (from MiscData table in source databases)
-- One record per aircraft logbook set. The Stearman dataset has one aircraft.
-- ---------------------------------------------------------------------------
CREATE TABLE Aircraft (
    AircraftID INT IDENTITY(1,1) PRIMARY KEY,
    Name NVARCHAR(100) NOT NULL,             -- 'Stearman'
    Owner NVARCHAR(255),                     -- 'Russ Aviation'
    DateCreated DATE,                        -- Original LBCD creation date
    SourceValidationKey NVARCHAR(100),       -- Original LBCD ValidationKey UUID
    CreatedAt DATETIME2 DEFAULT GETUTCDATE()
);

-- ---------------------------------------------------------------------------
-- Disc provenance tracking
-- Records the origin of each source MDB file for audit and traceability.
-- ---------------------------------------------------------------------------
CREATE TABLE Discs (
    DiscID INT PRIMARY KEY,                  -- 1-4 (matches source disc number)
    SourceFileName NVARCHAR(500),            -- Original .lbc filename
    DatabaseSizeMB INT,                      -- Size of the source MDB file
    ImageCount INT,                          -- Number of images on this disc
    BundleCount INT,                         -- Number of bundles on this disc
    IndexRecordCount INT,                    -- ImageIndexes + BundleIndexes count
    DateCreated DATE,                        -- From MiscData.DateCreated
    ImportedAt DATETIME2 DEFAULT GETUTCDATE()
);

-- ---------------------------------------------------------------------------
-- Hierarchical folder structure
-- Merges folders from all 4 discs. SERVICE MANUAL folders are combined;
-- Frame Drawing folders (A-N) remain separate as they are unique per disc.
-- ---------------------------------------------------------------------------
CREATE TABLE Folders (
    FolderID INT IDENTITY(1,1) PRIMARY KEY,
    AircraftID INT NOT NULL REFERENCES Aircraft(AircraftID),
    ParentFolderID INT NULL REFERENCES Folders(FolderID),
    SourceDiscNumber INT NOT NULL REFERENCES Discs(DiscID),
    SourceFolderID INT NOT NULL,             -- Original FolderID in source disc
    FolderName NVARCHAR(255) NOT NULL,
    SortOrder INT DEFAULT 0,
    Notes NVARCHAR(MAX),
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    UNIQUE (AircraftID, SourceDiscNumber, SourceFolderID)
);

-- ---------------------------------------------------------------------------
-- Bundle groups (multi-page documents)
-- Images sharing the same ImagePosition in a folder are grouped into bundles.
-- e.g., a 3-sheet assembly drawing: BundleOffset 1, 2, 3.
-- ---------------------------------------------------------------------------
CREATE TABLE Bundles (
    BundleID INT IDENTITY(1,1) PRIMARY KEY,
    FolderID INT NOT NULL REFERENCES Folders(FolderID),
    ImagePosition INT NOT NULL,              -- Bundle's position in folder view
    Notes NVARCHAR(MAX),
    SourceDiscNumber INT NOT NULL REFERENCES Discs(DiscID),
    SourceBundleID INT NOT NULL,             -- Original BundleID in source disc
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    UNIQUE (SourceDiscNumber, SourceBundleID)
);

-- ---------------------------------------------------------------------------
-- Image metadata
-- BLOBs (TIFFs, thumbnails) stored in Azure Blob Storage; paths referenced here.
-- Each image preserves its source disc number and original ID for provenance.
-- ---------------------------------------------------------------------------
CREATE TABLE Images (
    ImageID INT IDENTITY(1,1) PRIMARY KEY,
    FolderID INT NOT NULL REFERENCES Folders(FolderID),
    BundleID INT NULL REFERENCES Bundles(BundleID),
    BundleOffset INT NULL,                   -- Position within bundle (1-based), NULL if standalone
    ImagePosition INT NOT NULL,              -- Display order within folder
    OriginalFileName NVARCHAR(255),          -- e.g. 'A FRAME DRAWINGS(001).tif'
    BlobPath NVARCHAR(500) NOT NULL,         -- Azure Blob: originals/disc{N}/{ImageID}.tif
    TilePath NVARCHAR(500),                  -- Azure Blob: tiles/{ImageID}/ (DZI directory)
    ThumbnailPath NVARCHAR(500),             -- Azure Blob: thumbnails/{ImageID}.jpg
    ImageWidth INT,                          -- Pixels (typically ~12000)
    ImageHeight INT,                         -- Pixels (typically ~9000)
    FileSizeBytes BIGINT,                    -- Original TIFF file size
    MimeType NVARCHAR(50) DEFAULT 'image/tiff',
    Sha256Hash NVARCHAR(64),                 -- SHA-256 of original TIFF for integrity verification
    OcrText NVARCHAR(MAX),                   -- Future: OCR-extracted text from the drawing
    Notes NVARCHAR(MAX),                     -- User annotations
    SourceDiscNumber INT NOT NULL REFERENCES Discs(DiscID),
    SourceImageID INT NOT NULL,              -- Original ImageID in source disc
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    ModifiedAt DATETIME2,
    UNIQUE (SourceDiscNumber, SourceImageID)
);

-- ---------------------------------------------------------------------------
-- Index type definitions
-- Two types inherited from LBCD: Drawing # (DG) and Key Word (KW).
-- ---------------------------------------------------------------------------
CREATE TABLE IndexTypes (
    IndexTypeID INT PRIMARY KEY,             -- 1=Drawing#, 2=KeyWord
    Name NVARCHAR(50) NOT NULL,              -- 'Drawing #', 'Key Word'
    Code NVARCHAR(10) NOT NULL,              -- 'DG', 'KW'
    UNIQUE (Code)
);

-- ---------------------------------------------------------------------------
-- Per-image search indexes
-- Each image has multiple index records (Drawing #s and Key Words).
-- Example: Image 1 -> Drawing # '73-1000', Key Word 'BLOCK', Key Word 'STANDARD TITLE'
-- ---------------------------------------------------------------------------
CREATE TABLE ImageIndexes (
    ImageIndexID INT IDENTITY(1,1) PRIMARY KEY,
    ImageID INT NOT NULL REFERENCES Images(ImageID),
    IndexTypeID INT NOT NULL REFERENCES IndexTypes(IndexTypeID),
    IndexValue NVARCHAR(100) NOT NULL,       -- Expanded from source 40 chars
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    INDEX IX_ImageIndexes_Value NONCLUSTERED (IndexValue),
    INDEX IX_ImageIndexes_TypeValue NONCLUSTERED (IndexTypeID, IndexValue)
);

-- ---------------------------------------------------------------------------
-- Per-bundle search indexes
-- When a bundle has indexes, all images in that bundle share those values.
-- ---------------------------------------------------------------------------
CREATE TABLE BundleIndexes (
    BundleIndexID INT IDENTITY(1,1) PRIMARY KEY,
    BundleID INT NOT NULL REFERENCES Bundles(BundleID),
    IndexTypeID INT NOT NULL REFERENCES IndexTypes(IndexTypeID),
    IndexValue NVARCHAR(100) NOT NULL,
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    INDEX IX_BundleIndexes_Value NONCLUSTERED (IndexValue)
);

-- ---------------------------------------------------------------------------
-- Users (WorkOS/Entra ID user mapping)
-- ---------------------------------------------------------------------------
CREATE TABLE Users (
    UserID NVARCHAR(128) PRIMARY KEY,        -- WorkOS or Entra ID user identifier
    Email NVARCHAR(255) NOT NULL,
    FirstName NVARCHAR(100),
    LastName NVARCHAR(100),
    AccessTierID INT NOT NULL DEFAULT 1,
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    LastLoginAt DATETIME2,
    CONSTRAINT FK_Users_AccessTiers
        FOREIGN KEY (AccessTierID) REFERENCES AccessTiers(AccessTierID)
);

-- ---------------------------------------------------------------------------
-- Audit log
-- Tracks all user interactions for regulatory compliance (FAA/EASA).
-- Aviation engineering records require chain-of-custody documentation.
-- ---------------------------------------------------------------------------
CREATE TABLE AuditLog (
    AuditID BIGINT IDENTITY(1,1) PRIMARY KEY,
    UserID NVARCHAR(128),
    Action NVARCHAR(50) NOT NULL,            -- VIEW, SEARCH, DOWNLOAD, NOTE_EDIT, LOGIN
    EntityType NVARCHAR(50),                 -- Image, Bundle, Folder
    EntityID INT,
    Details NVARCHAR(MAX),                   -- JSON: search query, download format, etc.
    IPAddress NVARCHAR(45),                  -- IPv4 or IPv6
    UserAgent NVARCHAR(500),
    Timestamp DATETIME2 DEFAULT GETUTCDATE(),
    INDEX IX_AuditLog_User NONCLUSTERED (UserID, Timestamp),
    INDEX IX_AuditLog_Action NONCLUSTERED (Action, Timestamp),
    INDEX IX_AuditLog_Entity NONCLUSTERED (EntityType, EntityID)
);


-- =============================================================================
-- Additional indexes for common query patterns
-- =============================================================================

-- Folder lookups by aircraft and parent (tree navigation)
CREATE NONCLUSTERED INDEX IX_Folders_AircraftParent
    ON Folders (AircraftID, ParentFolderID)
    INCLUDE (FolderName, SortOrder);

-- Image lookups by folder (thumbnail grid view)
CREATE NONCLUSTERED INDEX IX_Images_Folder
    ON Images (FolderID, ImagePosition)
    INCLUDE (ThumbnailPath, OriginalFileName, BundleID);

-- Image lookups by bundle (multi-page document carousel)
CREATE NONCLUSTERED INDEX IX_Images_Bundle
    ON Images (BundleID, BundleOffset)
    INCLUDE (BlobPath, ThumbnailPath, OriginalFileName);

-- Bundle lookups by folder
CREATE NONCLUSTERED INDEX IX_Bundles_Folder
    ON Bundles (FolderID, ImagePosition);

-- Image index lookups by image (detail view: show all indexes for an image)
CREATE NONCLUSTERED INDEX IX_ImageIndexes_ImageID
    ON ImageIndexes (ImageID)
    INCLUDE (IndexTypeID, IndexValue);

-- Bundle index lookups by bundle
CREATE NONCLUSTERED INDEX IX_BundleIndexes_BundleID
    ON BundleIndexes (BundleID)
    INCLUDE (IndexTypeID, IndexValue);

-- Provenance queries (find images from a specific source disc)
CREATE NONCLUSTERED INDEX IX_Images_Source
    ON Images (SourceDiscNumber, SourceImageID);

-- User login tracking
CREATE NONCLUSTERED INDEX IX_Users_Email
    ON Users (Email);

-- Audit log date-range queries
CREATE NONCLUSTERED INDEX IX_AuditLog_Timestamp
    ON AuditLog (Timestamp)
    INCLUDE (UserID, Action);


-- =============================================================================
-- View: Unified search results
-- Combines image metadata, folder path, and all search indexes into a single
-- queryable view for the search API.
-- =============================================================================
CREATE VIEW vw_SearchResults AS
SELECT
    i.ImageID,
    i.FolderID,
    f.FolderName,
    pf.FolderName AS ParentFolderName,
    i.BundleID,
    i.BundleOffset,
    i.ImagePosition,
    i.OriginalFileName,
    i.BlobPath,
    i.TilePath,
    i.ThumbnailPath,
    i.ImageWidth,
    i.ImageHeight,
    i.FileSizeBytes,
    i.MimeType,
    i.Sha256Hash,
    i.OcrText,
    i.Notes,
    i.SourceDiscNumber,
    i.SourceImageID,
    ix.IndexTypeID,
    it.Name AS IndexTypeName,
    it.Code AS IndexTypeCode,
    ix.IndexValue
FROM Images i
INNER JOIN Folders f ON i.FolderID = f.FolderID
LEFT JOIN Folders pf ON f.ParentFolderID = pf.FolderID
LEFT JOIN ImageIndexes ix ON i.ImageID = ix.ImageID
LEFT JOIN IndexTypes it ON ix.IndexTypeID = it.IndexTypeID;
GO

-- =============================================================================
-- View: Bundle detail with all member images
-- Shows each bundle with its images and combined indexes.
-- =============================================================================
CREATE VIEW vw_BundleDetail AS
SELECT
    b.BundleID,
    b.FolderID,
    f.FolderName,
    b.ImagePosition AS BundlePosition,
    b.Notes AS BundleNotes,
    b.SourceDiscNumber,
    b.SourceBundleID,
    i.ImageID,
    i.BundleOffset,
    i.OriginalFileName,
    i.BlobPath,
    i.ThumbnailPath,
    i.ImageWidth,
    i.ImageHeight,
    bi.IndexTypeID AS BundleIndexTypeID,
    bit2.Name AS BundleIndexTypeName,
    bi.IndexValue AS BundleIndexValue
FROM Bundles b
INNER JOIN Folders f ON b.FolderID = f.FolderID
LEFT JOIN Images i ON i.BundleID = b.BundleID
LEFT JOIN BundleIndexes bi ON b.BundleID = bi.BundleID
LEFT JOIN IndexTypes bit2 ON bi.IndexTypeID = bit2.IndexTypeID;
GO

-- =============================================================================
-- View: Folder tree with image counts
-- Provides folder hierarchy with aggregate counts for the navigation tree.
-- =============================================================================
CREATE VIEW vw_FolderTree AS
SELECT
    f.FolderID,
    f.AircraftID,
    f.ParentFolderID,
    f.FolderName,
    f.SortOrder,
    f.SourceDiscNumber,
    a.Name AS AircraftName,
    pf.FolderName AS ParentFolderName,
    (SELECT COUNT(*) FROM Images WHERE FolderID = f.FolderID) AS ImageCount,
    (SELECT COUNT(*) FROM Bundles WHERE FolderID = f.FolderID) AS BundleCount
FROM Folders f
INNER JOIN Aircraft a ON f.AircraftID = a.AircraftID
LEFT JOIN Folders pf ON f.ParentFolderID = pf.FolderID;
GO


-- =============================================================================
-- Seed data
-- =============================================================================

-- Index types (matches source LBCD IndexTypes table exactly)
INSERT INTO IndexTypes (IndexTypeID, Name, Code) VALUES (1, 'Drawing #', 'DG');
INSERT INTO IndexTypes (IndexTypeID, Name, Code) VALUES (2, 'Key Word', 'KW');

-- Access tiers
INSERT INTO AccessTiers (Name, Description, MaxImagesPerDay, CanDownloadOriginals, CanExportPDF) VALUES
    ('free', 'Free access - all content viewable', NULL, 1, 1),
    ('paid', 'Paid tier - reserved for future premium features', NULL, 1, 1),
    ('admin', 'Administrator - full access', NULL, 1, 1);

-- Aircraft record (from MiscData across all 4 source discs)
INSERT INTO Aircraft (Name, Owner, DateCreated, SourceValidationKey) VALUES
    ('Stearman', 'Russ Aviation', '2001-05-23', 'B4F93241-9C86-11d4-AEA6-0000863547E9');


-- =============================================================================
-- Full-text search catalog
-- Enables full-text queries on notes and OCR text fields.
-- =============================================================================
-- NOTE: Full-text indexing requires the Azure SQL full-text feature to be
-- enabled. These statements may need adjustment based on your Azure SQL tier.
--
-- CREATE FULLTEXT CATALOG StearmanFT;
-- CREATE FULLTEXT INDEX ON Images (Notes, OcrText)
--     KEY INDEX PK__Images__7516F4EC ON StearmanFT
--     WITH STOPLIST = SYSTEM;
-- CREATE FULLTEXT INDEX ON ImageIndexes (IndexValue)
--     KEY INDEX PK__ImageInd__01271E4B ON StearmanFT
--     WITH STOPLIST = SYSTEM;
-- CREATE FULLTEXT INDEX ON BundleIndexes (IndexValue)
--     KEY INDEX PK__BundleIn__3EC5D77F ON StearmanFT
--     WITH STOPLIST = SYSTEM;
