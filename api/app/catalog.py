"""Stearman content catalog — master index of all library resources.

Every item references a blob in Azure Storage. Categories follow the
agreed taxonomy. Keep this file as the single source of truth for
content metadata; the API reads it at startup.

To add new content: append an entry here, upload the blob, done.

DOMAIN NOTE: No domain names are hardcoded here. The API constructs
all URLs dynamically using SITE_BASE_URL from config.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CatalogItem(BaseModel):
    id: str
    title: str
    description: str
    category: str
    subcategory: str = ""
    container: str  # blob storage container
    blob_path: str  # path within container
    content_type: str  # pdf, image, video, markdown, text
    size_mb: float = 0
    tags: list[str] = Field(default_factory=list)
    source: str = ""  # attribution / origin
    year: int | None = None  # publication year if known
    models: list[str] = Field(default_factory=list)  # aircraft models covered


# ── Official Manuals ──────────────────────────────────────────────────

OFFICIAL_MANUALS = [
    CatalogItem(
        id="erection-maintenance-pt13d-n2s5",
        title="Erection & Maintenance Instructions",
        description="Complete erection, rigging, and maintenance procedures for Army Model PT-13D and Navy Model N2S-5.",
        category="Official Manuals",
        container="manuals",
        blob_path="Stearman_Erection_and_Maintenance_Instructions_PT-13D_N2S-5.pdf",
        content_type="pdf",
        size_mb=23,
        tags=["erection", "maintenance", "rigging"],
        source="U.S. Government (public domain)",
        models=["PT-13D", "N2S-5"],
    ),
    CatalogItem(
        id="erection-maintenance-n2s5-full",
        title="Erection & Maintenance Instructions (Navy, Full)",
        description="Navy edition with additional detail for N2S-5 airplanes.",
        category="Official Manuals",
        container="reference-archive",
        blob_path="stearman-aero/Erection_and_Maintenance_Instructions_for_Navy_Model_N2S-5_Airplanes.pdf",
        content_type="pdf",
        size_mb=87,
        tags=["erection", "maintenance", "navy"],
        source="stearman-aero.com (public domain)",
        models=["N2S-5"],
    ),
    CatalogItem(
        id="erection-maintenance-pt13d-n2s5-sa",
        title="Erection & Maintenance Instructions (stearman-aero)",
        description="Alternate scan of erection and maintenance instructions for PT-13D / N2S-5.",
        category="Official Manuals",
        container="reference-archive",
        blob_path="stearman-aero/Erection_and_Maintenance_Instructions_for_Army_Model_PT-13D_and_Navy_Model_N2S-5_Airplanes.pdf",
        content_type="pdf",
        size_mb=22,
        tags=["erection", "maintenance"],
        source="stearman-aero.com (public domain)",
        models=["PT-13D", "N2S-5"],
    ),
    CatalogItem(
        id="service-instructions-pt13b-17-18",
        title="Service Instructions",
        description="Service instructions for Army Models PT-13B, PT-17, and PT-18.",
        category="Official Manuals",
        container="reference-archive",
        blob_path="stearman-aero/Service_Instructions_for_Army_Models_PT-13B-17_and_-18.pdf",
        content_type="pdf",
        size_mb=20,
        tags=["service", "maintenance"],
        source="stearman-aero.com (public domain)",
        models=["PT-13B", "PT-17", "PT-18"],
    ),
    CatalogItem(
        id="structural-repair",
        title="Structural Repair Instructions",
        description="Structural repair procedures for Army Model PT-13D and Navy Model N2S-5.",
        category="Official Manuals",
        container="reference-archive",
        blob_path="stearman-aero/Structural_Repair_Instructions_for_Army_Model_PT-13D_and_Navy_Model_N2S-5_Airplanes.pdf",
        content_type="pdf",
        size_mb=10,
        tags=["structural", "repair", "sheet metal"],
        source="stearman-aero.com (public domain)",
        models=["PT-13D", "N2S-5"],
    ),
    CatalogItem(
        id="overhaul-handbook",
        title="Handbook of Overhaul Instructions",
        description="Complete overhaul procedures for PT-13B, PT-17, and PT-18 primary training airplanes.",
        category="Official Manuals",
        container="reference-archive",
        blob_path="stearman-aero/Handbook_of_Overhaul_Instructions_for_the_Models_PT-13B_PT-17_and_PT-18_Primary_Training_Airplanes.pdf",
        content_type="pdf",
        size_mb=4,
        tags=["overhaul", "rebuild"],
        source="stearman-aero.com (public domain)",
        models=["PT-13B", "PT-17", "PT-18"],
    ),
]

# ── Parts & Catalogs ──────────────────────────────────────────────────

PARTS_CATALOGS = [
    CatalogItem(
        id="parts-catalog-pt13d-n2s5",
        title="Parts Catalog (PT-13D / N2S-5)",
        description="Illustrated parts breakdown and part number reference for Army Model PT-13D and Navy Model N2S-5.",
        category="Parts & Catalogs",
        container="manuals",
        blob_path="Stearman_Parts_Catalog_PT-13D_N2S-5.pdf",
        content_type="pdf",
        size_mb=149,
        tags=["parts", "IPC", "part numbers"],
        source="Russ Aviation",
        models=["PT-13D", "N2S-5"],
    ),
    CatalogItem(
        id="parts-catalog-pt13b-17-18",
        title="Parts Catalog (PT-13B / PT-17 / PT-18)",
        description="Parts catalog for the earlier PT-13B, PT-17, and PT-18 models.",
        category="Parts & Catalogs",
        container="reference-archive",
        blob_path="stearman-aero/Parts_Catalog_for_the_Models_PT-13BPT17_and_PT-18_Primary_Training_Airplanes.pdf",
        content_type="pdf",
        size_mb=21,
        tags=["parts", "IPC", "part numbers"],
        source="stearman-aero.com (public domain)",
        models=["PT-13B", "PT-17", "PT-18"],
    ),
    CatalogItem(
        id="aircorps-parts-digital",
        title="Airframe Parts Catalog (Digital)",
        description="AirCorps Library digital parts catalog for Stearman airframes.",
        category="Parts & Catalogs",
        container="reference-archive",
        blob_path="aircorps/Stearman_Airframe_Parts_Catalog_Digital.pdf",
        content_type="pdf",
        size_mb=12,
        tags=["parts", "airframe", "digital"],
        source="AirCorps Library",
    ),
]

# ── Pilot Handbooks ───────────────────────────────────────────────────

PILOT_HANDBOOKS = [
    CatalogItem(
        id="pilot-fop-pt13d-n2s5",
        title="Pilot's Flight Operating Instructions (PT-13D / N2S-5)",
        description="Official pilot's flight operating instructions.",
        category="Pilot Handbooks",
        container="reference-archive",
        blob_path="stearman-aero/Pilots_Flight_Operating_Instructions_for_the_Army_Model_PT-13D_and_Navy_Model_N2S-5_Airplanes.pdf",
        content_type="pdf",
        size_mb=7,
        tags=["pilot", "operating", "flight"],
        source="stearman-aero.com (public domain)",
        models=["PT-13D", "N2S-5"],
    ),
    CatalogItem(
        id="pilot-handbook-n2s4",
        title="Pilot's Handbook (N2S-4)",
        description="Pilot's handbook for the Navy Model N2S-4.",
        category="Pilot Handbooks",
        container="reference-archive",
        blob_path="stearman-aero/Pilots_Handbook_for_Model_N2S-4_Airplanes.pdf",
        content_type="pdf",
        size_mb=1,
        tags=["pilot", "handbook"],
        source="stearman-aero.com (public domain)",
        models=["N2S-4"],
    ),
    CatalogItem(
        id="pilot-handbook-n2s3",
        title="Pilot's Handbook (N2S-3)",
        description="Pilot's handbook for the Navy Model N2S-3.",
        category="Pilot Handbooks",
        container="reference-archive",
        blob_path="stearman-aero/Pilots_Handbook_for_N2S-3.pdf",
        content_type="pdf",
        size_mb=1,
        tags=["pilot", "handbook"],
        source="stearman-aero.com (public domain)",
        models=["N2S-3"],
    ),
    CatalogItem(
        id="pilot-handbook-n2s1-2-3",
        title="Pilot's Handbook (N2S-1, N2S-2, N2S-3)",
        description="Combined pilot's handbook covering the N2S-1, N2S-2, and N2S-3 models.",
        category="Pilot Handbooks",
        container="reference-archive",
        blob_path="stearman-aero/Pilots_Handbook_for_Stearman_Airplanes_Models_N2S-1_N2S-2_and_N2S-3.pdf",
        content_type="pdf",
        size_mb=5,
        tags=["pilot", "handbook"],
        source="stearman-aero.com (public domain)",
        models=["N2S-1", "N2S-2", "N2S-3"],
    ),
]

# ── Training ──────────────────────────────────────────────────────────

TRAINING = [
    CatalogItem(
        id="aerobatics-general",
        title="Aerobatics Manual",
        description="General aerobatic procedures and techniques.",
        category="Training",
        subcategory="Aerobatics",
        container="reference-archive",
        blob_path="stearman-aero/Aerobatics.pdf",
        content_type="pdf",
        size_mb=3,
        tags=["aerobatics", "training"],
        source="stearman-aero.com",
    ),
    CatalogItem(
        id="aerobatics-army",
        title="Stearman Aerobatics — U.S. Army Air Corps",
        description="Army Air Corps aerobatic training procedures for the Stearman.",
        category="Training",
        subcategory="Aerobatics",
        container="reference-archive",
        blob_path="stearman-aero/Stearman_Aerobatics_-_US_Army_Air_Corps.PDF",
        content_type="pdf",
        size_mb=2,
        tags=["aerobatics", "army", "training"],
        source="stearman-aero.com (public domain)",
    ),
    CatalogItem(
        id="aerobatics-navy",
        title="Stearman Aerobatics — U.S. Navy",
        description="Navy aerobatic training procedures for the Stearman.",
        category="Training",
        subcategory="Aerobatics",
        container="reference-archive",
        blob_path="stearman-aero/Stearman_Aerobatics_-_US_Navy.pdf",
        content_type="pdf",
        size_mb=4,
        tags=["aerobatics", "navy", "training"],
        source="stearman-aero.com (public domain)",
    ),
    CatalogItem(
        id="formation-manual",
        title="Formation Flying Manual",
        description="Stearman formation flying manual.",
        category="Training",
        subcategory="Formation",
        container="reference-archive",
        blob_path="stearman-aero/Stearman_Formation_manual.PDF",
        content_type="pdf",
        size_mb=2,
        tags=["formation", "flying", "training"],
        source="stearman-aero.com",
    ),
    CatalogItem(
        id="formation-navy",
        title="Formation Flying — U.S. Navy",
        description="Navy formation flying procedures for the Stearman.",
        category="Training",
        subcategory="Formation",
        container="reference-archive",
        blob_path="stearman-aero/Stearman_Formation_Flying_-_US_Navy.PDF",
        content_type="pdf",
        size_mb=2,
        tags=["formation", "navy", "training"],
        source="stearman-aero.com (public domain)",
    ),
    CatalogItem(
        id="formation-4th-edition",
        title="Formation Flying Manual — 4th Edition",
        description="Comprehensive formation flying manual, 4th edition.",
        category="Training",
        subcategory="Formation",
        container="reference-archive",
        blob_path="stearman-aero/Formation_Flying_Manual_-_4th_edition.pdf",
        content_type="pdf",
        size_mb=7,
        tags=["formation", "training"],
        source="stearman-aero.com",
    ),
    CatalogItem(
        id="formation-briefing-guide",
        title="Formation Flying Briefing Guide",
        description="Quick reference briefing guide for formation flying.",
        category="Training",
        subcategory="Formation",
        container="reference-archive",
        blob_path="stearman-aero/Formation_Flying_Briefing_Guide.pdf",
        content_type="pdf",
        size_mb=0.1,
        tags=["formation", "briefing", "training"],
        source="stearman-aero.com",
    ),
    CatalogItem(
        id="formation-t6",
        title="Formation Flying in the North American T-6",
        description="Formation procedures for the T-6 Texan — applicable techniques for Stearman.",
        category="Training",
        subcategory="Formation",
        container="reference-archive",
        blob_path="stearman-aero/Formation_Flying_in_the_North_American_T-6.pdf",
        content_type="pdf",
        size_mb=2,
        tags=["formation", "T-6", "training"],
        source="stearman-aero.com",
    ),
    CatalogItem(
        id="formation-qualification",
        title="Formation Qualification Report",
        description="North American Trainer Association formation qualification report.",
        category="Training",
        subcategory="Formation",
        container="reference-archive",
        blob_path="stearman-aero/North_American_Trainer_Association_-_Formation_Qualification_Report.pdf",
        content_type="pdf",
        size_mb=1,
        tags=["formation", "qualification"],
        source="stearman-aero.com",
    ),
    CatalogItem(
        id="jlfc-operations",
        title="JLFC Operations Manual — 2nd Edition",
        description="Joint Light Formation Committee operations manual.",
        category="Training",
        subcategory="Formation",
        container="reference-archive",
        blob_path="stearman-aero/JLFC_Operations_Manual_-_2nd_Edition.pdf",
        content_type="pdf",
        size_mb=13,
        tags=["formation", "operations", "JLFC"],
        source="stearman-aero.com",
    ),
    CatalogItem(
        id="training-boeing-pt17",
        title="Boeing A75N1 PT-17 Training Manual",
        description="Original Boeing training manual for the A75N1 (PT-17).",
        category="Training",
        container="reference-archive",
        blob_path="training/Boeing_A75N1_PT17_Training_Manual.pdf",
        content_type="pdf",
        size_mb=1,
        tags=["training", "Boeing", "original"],
        source="Public domain",
        models=["PT-17", "A75N1"],
    ),
]

# ── Engine ────────────────────────────────────────────────────────────

ENGINE = [
    CatalogItem(
        id="continental-r670-overhaul",
        title="Continental W-670 / R-670 Overhaul Instructions",
        description="Overhaul instructions for the Continental W-670 and R-670 radial engines.",
        category="Engine",
        container="reference-archive",
        blob_path="engine/Continental_W-670_R-670_Overhaul_Instructions.pdf",
        content_type="pdf",
        size_mb=9,
        tags=["engine", "Continental", "R-670", "W-670", "overhaul"],
        source="Public domain",
    ),
    CatalogItem(
        id="engine-boeing-pt17-training",
        title="Boeing A75N1 PT-17 Engine Training Manual",
        description="Engine-focused training manual for the Boeing A75N1 (PT-17).",
        category="Engine",
        container="reference-archive",
        blob_path="engine/Boeing_A75N1_PT17_Training_Manual.pdf",
        content_type="pdf",
        size_mb=1,
        tags=["engine", "training", "Boeing"],
        source="Public domain",
        models=["PT-17"],
    ),
]

# ── Regulatory ────────────────────────────────────────────────────────

REGULATORY = [
    CatalogItem(
        id="tcds-a729",
        title="Type Certificate Data Sheet A-729",
        description="FAA TCDS for Boeing Stearman Model 75 series.",
        category="Regulatory",
        container="reference-archive",
        blob_path="faa/TCDS_A-729_Boeing_Stearman_Model_75.pdf",
        content_type="pdf",
        size_mb=1,
        tags=["FAA", "TCDS", "type certificate"],
        source="FAA (public domain)",
    ),
    CatalogItem(
        id="nz-type-acceptance",
        title="NZ Type Acceptance — Boeing 75 Series",
        description="New Zealand type acceptance document for the Boeing 75 series.",
        category="Regulatory",
        container="reference-archive",
        blob_path="faa/NZ_Type_Acceptance_Boeing_75_Series.pdf",
        content_type="pdf",
        size_mb=0.1,
        tags=["New Zealand", "type acceptance", "international"],
        source="NZ CAA",
    ),
    CatalogItem(
        id="nz-stearman-ads",
        title="NZ Stearman Airworthiness Directives",
        description="New Zealand airworthiness directives applicable to Stearman aircraft.",
        category="Regulatory",
        container="reference-archive",
        blob_path="faa/ads/NZ_Stearman_ADs.pdf",
        content_type="pdf",
        size_mb=0.1,
        tags=["AD", "airworthiness directive", "New Zealand"],
        source="NZ CAA",
    ),
]

# ── Safety (NTSB) ────────────────────────────────────────────────────

SAFETY = [
    CatalogItem(
        id=f"ntsb-{blob.split('_')[1].split('.')[0]}",
        title=f"NTSB Report {blob.split('_')[1].split('.')[0]}",
        description=f"NTSB accident/incident investigation report #{blob.split('_')[1].split('.')[0]}.",
        category="Safety",
        container="reference-archive",
        blob_path=f"ntsb/{blob}",
        content_type="pdf",
        size_mb=1,
        tags=["NTSB", "accident", "investigation", "safety"],
        source="NTSB (public domain)",
    )
    for blob in [
        "NTSB_101923.pdf", "NTSB_46678.pdf", "NTSB_46919.pdf",
        "NTSB_51068.pdf", "NTSB_83621.pdf", "NTSB_93898.pdf", "NTSB_93959.pdf",
    ]
]

# ── Historical ────────────────────────────────────────────────────────

HISTORICAL = [
    CatalogItem(
        id="americas-fighting-planes",
        title="America's Fighting Planes in Action",
        description="Period publication featuring American military aircraft including the Stearman.",
        category="Historical",
        container="reference-archive",
        blob_path="internet_archive/docs/AmericasFightingPlanesInAction.pdf",
        content_type="pdf",
        size_mb=34,
        tags=["WWII", "historical", "magazine"],
        source="Internet Archive (public domain)",
    ),
    CatalogItem(
        id="highway-magazine-1949",
        title="Highway Magazine — September 1949",
        description="1949 magazine article featuring Stearman content.",
        category="Historical",
        container="reference-archive",
        blob_path="internet_archive/docs/highway-1949-09.pdf",
        content_type="pdf",
        size_mb=2,
        tags=["1949", "magazine", "historical"],
        source="Internet Archive (public domain)",
        year=1949,
    ),
]

# ── Aggregate Catalog ─────────────────────────────────────────────────

ALL_ITEMS: list[CatalogItem] = (
    OFFICIAL_MANUALS
    + PARTS_CATALOGS
    + PILOT_HANDBOOKS
    + TRAINING
    + ENGINE
    + REGULATORY
    + SAFETY
    + HISTORICAL
)

ITEMS_BY_ID = {item.id: item for item in ALL_ITEMS}

CATEGORIES = sorted(set(item.category for item in ALL_ITEMS))
