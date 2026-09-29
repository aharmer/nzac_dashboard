"""NZAC Project Dashboard — Streamlit port of the original R/Shiny app."""

import base64
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st
import streamlit_authenticator as stauth
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from supabase import Client, create_client

APP_NAME = "NZAC Project Dashboard"
APP_VER = "2.0"
GITHUB_LINK = "https://github.com/aharmer/nzac_dashboard"
ACCENT = "#3f9c82"

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"

NAMES_TABLE = "names"
TAXON_RANKS = ["genus", "species", "subspecies"]
YES_NO = ["yes", "no"]
ORIGIN_OPTIONS = ["Endemic", "Exotic", "Indigenous", "Uncertain"]
OCCURRENCE_OPTIONS = [
    "Absent", "Captive", "Eradicated", "Extinct",
    "Recorded in error", "Uncertain", "Vagrant", "Wild",
]
# (db column, public display label)
NAMES_PUBLIC_COLUMNS = [
    ("part_name", "PartName"),
    ("is_accepted", "IsAccepted"),
    ("accepted_name", "AcceptedName"),
    ("is_original", "IsOriginal"),
    ("original_name", "OriginalName"),
    ("authors", "Authors"),
    ("year_of_publication", "YearOfPublication"),
    ("authority_and_year", "AuthorityAndYear"),
    ("taxon_rank", "TaxonRank"),
    ("phylum", "Phylum"),
    ("class", "Class"),
    ("order_name", "Order"),
    ("superfamily", "Superfamily"),
    ("family", "Family"),
    ("subfamily", "Subfamily"),
    ("tribe", "Tribe"),
    ("genus", "Genus"),
    ("subgenus", "Subgenus"),
    ("species", "Species"),
    ("full_name", "FullName"),
    ("common_name", "CommonName"),
    ("origin", "Origin"),
    ("occurrence", "Occurrence"),
    ("doc_threat_status", "DocThreatStatus"),
    ("nomenclatural_code", "NomenclaturalCode"),
    ("page", "Page"),
    ("taxonomic_notes", "TaxonomicNotes"),
    ("name_variation", "NameVariation"),
    ("primary_reference", "PrimaryReference"),
]
NAMES_EMPTY_DF = pd.DataFrame(columns=[c for c, _ in NAMES_PUBLIC_COLUMNS])

# (db column, template display label) -- excludes auto-generated fields
# (part_name, authority_and_year, full_name, phylum, nomenclatural_code)
BULK_TEMPLATE_COLUMNS = [
    ("genus", "Genus"),
    ("species", "Species"),
    ("authors", "Authors"),
    ("year_of_publication", "YearOfPublication"),
    ("taxon_rank", "TaxonRank"),
    ("is_accepted", "IsAccepted"),
    ("accepted_name", "AcceptedName"),
    ("is_original", "IsOriginal"),
    ("original_name", "OriginalName"),
    ("class", "Class"),
    ("order_name", "Order"),
    ("superfamily", "Superfamily"),
    ("family", "Family"),
    ("subfamily", "Subfamily"),
    ("tribe", "Tribe"),
    ("subgenus", "Subgenus"),
    ("common_name", "CommonName"),
    ("origin", "Origin"),
    ("occurrence", "Occurrence"),
    ("doc_threat_status", "DocThreatStatus"),
    ("taxonomic_notes", "TaxonomicNotes"),
    ("name_variation", "NameVariation"),
    ("page", "Page"),
    ("primary_reference", "PrimaryReference"),
]
BULK_TEMPLATE_DROPDOWNS = {
    "TaxonRank": TAXON_RANKS,
    "IsAccepted": YES_NO,
    "IsOriginal": YES_NO,
    "Origin": ORIGIN_OPTIONS,
    "Occurrence": OCCURRENCE_OPTIONS,
}

# Per-column guidance for the bulk-upload template, adapted from the original
# NZAC names-entry workflow's "column descriptors" sheet.
# (db column, required?, guidance text)
BULK_FIELD_INFO = [
    ("genus", True, "Enter Genus (capitalise first letter)."),
    ("species", False, "Enter species epithet only (add a subspecies epithet after it if relevant). "
                        "Leave blank for genus-rank names. Do not add authority, tag names, 'sp.', or "
                        "abbreviations. Required for species/subspecies-rank names."),
    ("authors", True, "Enter the LAST name of author(s) only; do not add initials, year, or brackets."),
    ("year_of_publication", True, "4-digit year of publication."),
    ("taxon_rank", True, "One of: genus, species, subspecies."),
    ("is_accepted", True, "Is this the accepted name? yes or no."),
    ("accepted_name", False, "Required if IsAccepted = no: enter the accepted name."),
    ("is_original", True, "Is this the original combination (basionym)? yes or no."),
    ("original_name", False, "Required if IsOriginal = no: enter the original name."),
    ("class", True, "Enter Class."),
    ("order_name", True, "Enter Order."),
    ("superfamily", False, "Enter Superfamily."),
    ("family", True, "Enter Family."),
    ("subfamily", False, "Enter Subfamily."),
    ("tribe", False, "Enter Tribe."),
    ("subgenus", False, "Enter Subgenus."),
    ("common_name", False, "Common name(s); separate multiple names with a semicolon."),
    ("origin", True, "Endemic = only in NZ; Indigenous = native to NZ but also elsewhere; "
                      "Exotic = accidental or deliberate introduction (e.g. biocontrol); or Uncertain."),
    ("occurrence", True, "One of: Absent, Captive, Eradicated, Extinct, Recorded in error, Uncertain, "
                          "Vagrant, Wild."),
    ("doc_threat_status", False, "DOC threat classification, if applicable."),
    ("taxonomic_notes", False, "Any comment to clarify taxonomic status, or a tag name (e.g. spA)."),
    ("name_variation", False, "Any known variant spelling of the name."),
    ("page", False, "First page of the taxonomic description."),
    ("primary_reference", False, "Citation with author(s), year, title, journal etc."),
]

# Taxonomic hierarchy fields that can be used to select a group of matching
# records for a bulk edit (db column, display label).
RENAME_FIELDS = [
    ("genus", "Genus"),
    ("subgenus", "Subgenus"),
    ("tribe", "Tribe"),
    ("subfamily", "Subfamily"),
    ("family", "Family"),
    ("superfamily", "Superfamily"),
    ("order_name", "Order"),
    ("class", "Class"),
]

# Fields that can be bulk-set to a single new value across every selected record.
# (db column, display label, widget kind, [options if select]). Excludes fields
# that are auto-generated (PartName/AuthorityAndYear/FullName/Phylum/
# NomenclaturalCode -- recomputed automatically instead when relevant inputs
# change) or that are almost always different per-record even within a group
# (Species, AcceptedName, OriginalName, IsAccepted, CommonName).
BULK_EDITABLE_FIELDS = [
    ("genus", "Genus", "text"),
    ("subgenus", "Subgenus", "text"),
    ("authors", "Authors", "text"),
    ("year_of_publication", "YearOfPublication", "text"),
    ("is_original", "IsOriginal", "select", YES_NO),
    ("class", "Class", "text"),
    ("order_name", "Order", "text"),
    ("superfamily", "Superfamily", "text"),
    ("family", "Family", "text"),
    ("subfamily", "Subfamily", "text"),
    ("tribe", "Tribe", "text"),
    ("origin", "Origin", "select", ORIGIN_OPTIONS),
    ("occurrence", "Occurrence", "select", OCCURRENCE_OPTIONS),
    ("doc_threat_status", "DocThreatStatus", "text"),
    ("taxonomic_notes", "TaxonomicNotes", "text"),
    ("name_variation", "NameVariation", "text"),
    ("page", "Page", "text"),
    ("primary_reference", "PrimaryReference", "text"),
]
# Changing any of these means PartName/AuthorityAndYear/FullName must be recomputed.
BULK_EDIT_DERIVED_TRIGGERS = {"genus", "authors", "year_of_publication", "is_original"}

st.set_page_config(page_title=APP_NAME, page_icon=str(ASSETS_DIR / "NZAC_pare.png"), layout="wide")


# ---- Data loading -----------------------------------------------------------

@st.cache_data
def load_data():
    dat = pd.read_csv(DATA_DIR / "mass_digi.csv")
    dat = dat.loc[:, ~dat.columns.str.contains(r"^Unnamed")]
    dat.columns = [c.strip().lower() for c in dat.columns]
    dat["proportion"] = dat["digitised"] / dat["inventory"]

    loc = pd.read_csv(DATA_DIR / "georefs.csv")

    prog = pd.read_csv(DATA_DIR / "annual_progress.csv")
    prog["digitised"] = prog["digitised"].astype(str).str.replace(",", "").astype(int)
    prog["increase"] = prog["increase"].astype(str).str.replace(",", "").astype(int)
    prog["year"] = pd.to_datetime(prog["year"], format="%Y")

    summary_tab = pd.read_csv(DATA_DIR / "summary_table.csv", skipinitialspace=True)
    for col in ["Holdings", "Digitised"]:
        summary_tab[col] = summary_tab[col].astype(str).str.strip().str.replace(",", "").astype(int).map("{:,}".format)

    return dat, loc, prog, summary_tab


dat, loc, prog, summary_tab = load_data()


# ---- Names database: Supabase + auth helpers --------------------------------

@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])


@st.cache_data(ttl=300)
def load_names() -> pd.DataFrame:
    response = get_supabase_client().table(NAMES_TABLE).select("*").order("part_name").execute()
    if not response.data:
        return NAMES_EMPTY_DF.copy()
    return pd.DataFrame(response.data)


def get_authenticator():
    auth_cfg = st.secrets.get("auth")
    if not auth_cfg or "usernames" not in auth_cfg:
        return None
    credentials = {
        "usernames": {
            username: {"name": info["name"], "password": info["password"]}
            for username, info in auth_cfg["usernames"].items()
        }
    }
    return stauth.Authenticate(
        credentials,
        auth_cfg.get("cookie_name", "nzac_names_db"),
        auth_cfg.get("cookie_key", "changeme"),
        auth_cfg.get("cookie_expiry_days", 30),
    )


def _s(value) -> str:
    """Safely stringify a value that may be a pandas NaN/None (e.g. a SQL NULL read
    back from Supabase) for use as a text widget default or in an f-string. Plain
    `value or ""` is not safe here: NaN is truthy in Python, so it survives an
    `or` fallback and ends up literally interpolated as the string "nan"."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def compute_derived_fields(
    genus: str, species: str, authors: str, year: str, is_original: str
) -> tuple[str, str, str]:
    """PartName, AuthorityAndYear, and FullName are never entered directly -- they're
    always computed from Genus/Species/Authors/Year/IsOriginal, whether from the
    single-entry form, a bulk upload row, or a bulk edit that touches any of those
    fields."""
    genus = (genus or "").strip()
    species = (species or "").strip()
    part_name = f"{genus} {species}".strip() if species else genus
    authority_and_year = f"{authors}, {year}"
    if is_original == "no":
        authority_and_year = f"({authority_and_year})"
    full_name = f"{part_name} {authority_and_year}"
    return part_name, authority_and_year, full_name


def validate_and_build_record(fields: dict) -> tuple[dict | None, list[str]]:
    """Validate a raw {db_column: value} dict (as typed in the form or read from a
    bulk-upload row) and, if valid, return the fully-prepared record ready to
    insert/update -- with PartName/AuthorityAndYear/FullName/Phylum/NomenclaturalCode
    computed. Returns (None, errors) if anything essential/dependent is missing or
    invalid."""

    def clean(key: str) -> str:
        return str(fields.get(key) or "").strip()

    genus = clean("genus")
    species = clean("species")
    authors = clean("authors")
    year_raw = clean("year_of_publication")
    taxon_rank = clean("taxon_rank").lower()
    is_accepted = clean("is_accepted").lower()
    accepted_name = clean("accepted_name")
    is_original = clean("is_original").lower()
    original_name = clean("original_name")
    class_ = clean("class")
    order_name_val = clean("order_name")
    family = clean("family")
    origin = clean("origin")
    occurrence = clean("occurrence")

    errors = []
    if not genus:
        errors.append("Genus is required.")
    if taxon_rank not in TAXON_RANKS:
        errors.append(f"Taxon rank must be one of: {', '.join(TAXON_RANKS)}.")
    elif taxon_rank != "genus" and not species:
        errors.append("Species is required for species/subspecies-rank names.")
    if not authors:
        errors.append("Authors is required.")
    if not (year_raw.isdigit() and len(year_raw) == 4):
        errors.append("Year of publication must be a 4-digit number.")
    if is_accepted not in YES_NO:
        errors.append("Is accepted must be 'yes' or 'no'.")
    elif is_accepted == "no" and not accepted_name:
        errors.append("Accepted name is required when the name is not accepted.")
    if is_original not in YES_NO:
        errors.append("Is original must be 'yes' or 'no'.")
    elif is_original == "no" and not original_name:
        errors.append("Original name is required when this isn't the original combination.")
    if not class_:
        errors.append("Class is required.")
    if not order_name_val:
        errors.append("Order is required.")
    if not family:
        errors.append("Family is required.")
    if origin not in ORIGIN_OPTIONS:
        errors.append(f"Origin must be one of: {', '.join(ORIGIN_OPTIONS)}.")
    if occurrence not in OCCURRENCE_OPTIONS:
        errors.append(f"Occurrence must be one of: {', '.join(OCCURRENCE_OPTIONS)}.")

    if errors:
        return None, errors

    part_name, authority_and_year, full_name = compute_derived_fields(
        genus, species, authors, year_raw, is_original
    )

    record = {
        "part_name": part_name,
        "is_accepted": is_accepted == "yes",
        "accepted_name": accepted_name or None,
        "is_original": is_original == "yes",
        "original_name": original_name or None,
        "authors": authors,
        "year_of_publication": int(year_raw),
        "authority_and_year": authority_and_year,
        "taxon_rank": taxon_rank,
        "phylum": "Animalia",
        "class": class_,
        "order_name": order_name_val,
        "superfamily": clean("superfamily") or None,
        "family": family,
        "subfamily": clean("subfamily") or None,
        "tribe": clean("tribe") or None,
        "genus": genus,
        "subgenus": clean("subgenus") or None,
        "species": species or None,
        "full_name": full_name,
        "common_name": clean("common_name") or None,
        "origin": origin,
        "occurrence": occurrence,
        "doc_threat_status": clean("doc_threat_status") or None,
        "nomenclatural_code": "ICZN",
        "taxonomic_notes": clean("taxonomic_notes") or None,
        "name_variation": clean("name_variation") or None,
        "page": clean("page") or None,
        "primary_reference": clean("primary_reference") or None,
    }
    return record, []


NAMES_UPLOAD_SHEET = "new names"

REQUIRED_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
HEADER_FONT = Font(bold=True)


def build_names_template_xlsx() -> bytes:
    """An .xlsx template for bulk-uploading new names: an Instructions sheet
    explaining the workflow and every column (adapted from the original NZAC
    names-entry spreadsheet), plus the data-entry sheet itself with dropdown
    validation and required columns highlighted."""
    field_info = dict((col, (required, guidance)) for col, required, guidance in BULK_FIELD_INFO)
    headers = [label for _, label in BULK_TEMPLATE_COLUMNS]

    wb = Workbook()

    # ---- Instructions sheet ----
    instructions = wb.active
    instructions.title = "Instructions"
    instructions.sheet_view.showGridLines = False
    instructions.column_dimensions["A"].width = 22
    instructions.column_dimensions["B"].width = 12
    instructions.column_dimensions["C"].width = 90

    instructions["A1"] = "Bulk upload: new names"
    instructions["A1"].font = Font(bold=True, size=14)
    intro_lines = [
        "Use this to add a batch of NEW names to the NZAC Names Database at once -- e.g. "
        "when a paper describing several new species is published.",
        "Fill in one row per new name on the '" + NAMES_UPLOAD_SHEET + "' sheet, then upload this "
        "file back into the app.",
        "This only ADDS new names -- to change an existing name, use 'Add / update a name' or "
        "'Bulk edit a group' in the app instead.",
        "Only record names that have, at some stage, been published as valid names -- not "
        "undescribed 'tag names' or diversity estimates.",
        "PartName, AuthorityAndYear, FullName, Phylum, and NomenclaturalCode are generated "
        "automatically -- don't include them here.",
    ]
    row = 3
    for line in intro_lines:
        cell = instructions.cell(row=row, column=1, value=line)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        instructions.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
        instructions.row_dimensions[row].height = 30
        row += 2

    row += 1
    for col_idx, title in enumerate(["Column", "Required?", "Guidance"], start=1):
        cell = instructions.cell(row=row, column=col_idx, value=title)
        cell.font = HEADER_FONT
    instructions.freeze_panes = f"A{row + 1}"
    row += 1
    for db_col, label in BULK_TEMPLATE_COLUMNS:
        required, guidance = field_info[db_col]
        instructions.cell(row=row, column=1, value=label)
        req_cell = instructions.cell(row=row, column=2, value="Required" if required else "Optional")
        if required:
            req_cell.font = Font(bold=True)
        guidance_cell = instructions.cell(row=row, column=3, value=guidance)
        guidance_cell.alignment = Alignment(wrap_text=True, vertical="top")
        row += 1

    # ---- Data-entry sheet ----
    ws = wb.create_sheet(NAMES_UPLOAD_SHEET)
    ws.append(headers)
    ws.freeze_panes = "A2"

    for col_idx, (db_col, label) in enumerate(BULK_TEMPLATE_COLUMNS, start=1):
        required, guidance = field_info[db_col]
        cell = ws.cell(row=1, column=col_idx)
        cell.font = HEADER_FONT
        if required:
            cell.fill = REQUIRED_FILL
        cell.comment = Comment(("Required. " if required else "Optional. ") + guidance, "NZAC Names Database")

    max_rows = 500
    for col_name, options in BULK_TEMPLATE_DROPDOWNS.items():
        col_idx = headers.index(col_name) + 1
        col_letter = ws.cell(row=1, column=col_idx).column_letter
        dv = DataValidation(type="list", formula1='"' + ",".join(options) + '"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f"{col_letter}2:{col_letter}{max_rows + 1}")

    for i, header in enumerate(headers, start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = max(14, len(header) + 2)

    wb.active = wb.sheetnames.index("Instructions")

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def parse_bulk_upload(uploaded_file) -> pd.DataFrame:
    if uploaded_file.name.lower().endswith(".csv"):
        raw = pd.read_csv(uploaded_file, dtype=str, keep_default_na=False)
    else:
        raw = pd.read_excel(
            uploaded_file, sheet_name=NAMES_UPLOAD_SHEET, dtype=str, engine="openpyxl", keep_default_na=False
        )
    raw.columns = [str(c).strip() for c in raw.columns]
    return raw


# ---- Styling (light theme is set in .streamlit/config.toml) -----------------

st.markdown(
    f"""
    <style>
    .kpi-box {{
        background: linear-gradient(145deg, #ffffff, #f0f2f6);
        border: 1px solid #dfe3e8;
        border-radius: 0.75rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.06);
        padding: 1.5rem;
        margin-bottom: 1rem;
        text-align: center;
    }}
    .kpi-box .kpi-value {{
        color: {ACCENT};
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }}
    .kpi-box .kpi-label {{
        color: #6b7280;
        font-size: 1rem;
        font-weight: 400;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


def kpi_box(value: str, label: str):
    st.markdown(
        f"""<div class="kpi-box"><div class="kpi-value">{value}</div>
        <div class="kpi-label">{label}</div></div>""",
        unsafe_allow_html=True,
    )


# ---- Header ------------------------------------------------------------

_logo_b64 = base64.b64encode((ASSETS_DIR / "NZAC_pare.png").read_bytes()).decode()
st.markdown(
    f"""
    <div style="display:flex; align-items:center; gap:1rem; border-bottom:2px solid #dfe3e8;
                padding-bottom:1rem; margin-bottom:1rem;">
        <a href="https://www.landcareresearch.co.nz/tools-and-resources/collections/
           new-zealand-arthropod-collection-nzac/" target="_blank">
            <img src="data:image/png;base64,{_logo_b64}" alt="MWLR Logo" title="NZAC Pare" height="60">
        </a>
        <h1 style="margin:0;">{APP_NAME}</h1>
    </div>
    """,
    unsafe_allow_html=True,
)

MAIN_SECTIONS = ["Summary", "Projects", "Digitisation progress by taxa", "Names database", "Maps"]
# Deliberately st.segmented_control rather than st.tabs(): Streamlit's st.tabs()
# tracks the active tab by element position on the frontend rather than real
# state. The Names database section's content changes shape a lot at runtime
# (forms/tables appearing and disappearing as you make selections), and that
# was enough to desync st.tabs()'s position tracking, causing another tab's
# content (e.g. the Maps section) to render inside the wrong panel. A
# segmented_control with a key uses real session state instead, so it doesn't
# have this failure mode, while still looking and behaving like a tab bar.
active_section = st.segmented_control(
    "Section",
    MAIN_SECTIONS,
    default=MAIN_SECTIONS[0],
    required=True,
    key="main_section",
    label_visibility="collapsed",
    width="stretch",
)
st.divider()


# ---- Section: Summary -----------------------------------------------------------

if active_section == "Summary":
    total_row = summary_tab.loc[summary_tab["Material type"] == "Total"].iloc[0]
    total_dig = int(str(total_row["Digitised"]).replace(",", ""))
    pct_dig = int(str(total_row["Proportion Digitised"]).replace("%", ""))
    total_imaged = 3307

    k1, k2, k3 = st.columns(3)
    with k1:
        kpi_box(f"{total_dig:,}", "Specimens digitised")
    with k2:
        kpi_box(f"{pct_dig}%", "Of collection digitised")
    with k3:
        kpi_box(f"{total_imaged:,}", "Specimens imaged")

    st.subheader("New Zealand Arthropod Collection - Ko te Aitanga Pepeke o Aotearoa")
    st.markdown(
        "The intent of this site is to summarise projects across "
        "the New Zealand Arthropod Collection."
    )
    st.markdown(
        "The NZAC has the most complete coverage of terrestrial invertebrates in New "
        "Zealand. In addition to its fundamental value for the science of taxonomy and "
        "systematics, the collection helps underpin biosecurity decisions (e.g., verifying "
        "the presence or absence of species in New Zealand for the EPA, or confirming the "
        "identity of newly arrived species for MPI). The collection makes important "
        "contributions to conservation by identifying threatened species in collaboration "
        "with the Department of Conservation. The NZAC also holds a large collection of "
        "specimens on behalf of Pacific Island nations. There are 1.5+ million objects in "
        "the collection, comprising 7 million individual specimens, with 1.2+ million "
        "pinned specimens. There are more than 4100 primary types."
    )
    st.markdown(
        "For digitised specimens, further details can be found by searching the "
        '<a href="https://scd.landcareresearch.co.nz/Search?collectionId=NZAC" target="_blank">'
        "Systematics Collection Portal</a> or "
        '<a href="https://www.gbif.org/dataset/6e4b215e-9019-4934-8433-65d80a35c230" target="_blank">'
        "GBIF</a>.",
        unsafe_allow_html=True,
    )

    plot_col, table_col = st.columns(2)

    with plot_col:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=prog["year"],
                y=prog["digitised"],
                mode="lines+markers",
                line=dict(color="#9aa1ac", width=3),
                marker=dict(color=ACCENT, size=14, line=dict(color=ACCENT, width=1)),
                hovertemplate="%{x|%Y}: %{y:,}<extra></extra>",
            )
        )
        fig.update_layout(
            template="plotly_white",
            paper_bgcolor="#ffffff",
            plot_bgcolor="#ffffff",
            yaxis_title="Total digitised",
            xaxis_title="",
            font=dict(color="#262730", size=14),
            xaxis=dict(dtick="M12", tickformat="%Y", gridcolor="#e5e7eb"),
            yaxis=dict(tickformat=",", gridcolor="#e5e7eb"),
            margin=dict(l=40, r=20, t=20, b=40),
            height=450,
        )
        st.plotly_chart(fig, width='stretch')

    with table_col:
        st.dataframe(summary_tab, hide_index=True, width='stretch', height=200)

    st.markdown(
        'Created and maintained by <a href="https://www.landcareresearch.co.nz/about-us/our-people/aaron-harmer" '
        'target="_blank">Dr Aaron Harmer</a>.',
        unsafe_allow_html=True,
    )


# ---- Tab: Digitisation projects ---------------------------------------------

elif active_section == "Projects":
    img_col, text_col = st.columns([2, 4])
    with img_col:
        st.image(str(ASSETS_DIR / "rapiid.png"), width=500)
    with text_col:
        specimen_digitisation_overview = r"""
        ## Transforming specimen labels into digital data
        Natural history collections hold millions of physical specimens, each carrying handwritten or printed labels that record decades — sometimes centuries — of collecting effort. Turning that locked-away information into searchable, usable digital records has traditionally meant slow, error-prone manual transcription. This project takes on that bottleneck from two complementary angles: capturing better source images, and reading them intelligently.
 
        ### RAPIID — capturing the data at the source
        <a href="https://github.com/aharmer/RAPIID" target="_blank">RAPIID</a> is a desktop imaging application built for natural history collection digitisation workflows. It captures high-quality images of specimen labels using one or more cameras, decodes DataMatrix barcodes from accession labels on the fly, and automatically logs capture metadata to CSV and EXIF tags. No manual data entry is required at the imaging bench — every specimen is linked to its image and accession number the moment it's photographed.
 
        ### Chrysalis — reading the labels with AI
        <a href="https://chrysalis-ento.vercel.app/" target="_blank">Chrysalis</a> picks up where imaging leaves off. It's a browser-based tool that uses AI vision to digitise entomological specimen labels: upload images of pinned insect specimens, and Chrysalis automatically reads the labels and parses out locality, collector, date, and other curatorial fields. The result is a clean CSV ready to import straight into a collection management system, with human review built in to catch anything the model gets wrong.
 
        ### One workflow, start to finish
        Together, RAPIID and Chrysalis form an end-to-end pipeline for moving physical specimen data into digital form: RAPIID handles fast, accurate image capture and accession linking at the point of digitisation, while Chrysalis turns those images into structured, database-ready records. The goal in both cases is the same — give natural history collections professionals and researchers a way to digitise large batches of specimens quickly and accurately, without sacrificing data quality along the way.
        """
 
        st.markdown(specimen_digitisation_overview, unsafe_allow_html=True)


# ---- Tab: View progress by taxa ---------------------------------------------

elif active_section == "Digitisation progress by taxa":
    st.info(
        "There are four filters to access information: taxonomic order, family, origin, and "
        "material type. The five 'mega-diverse' insect orders (Coleoptera, Diptera, Hemiptera, "
        "Hymenoptera, Lepidoptera) have information at the family level. Information is not yet "
        "available at the family level for other taxonomic orders, or for specimens stored in "
        "fluid or on microscope slides (this information is presented only at the order level). "
        "For non-insects, information is a mix at the level of phylum, class, or order."
    )

    filt_col, results_col = st.columns([1, 3])

    with filt_col:
        order_choices = sorted(dat["order"].unique())
        order_sel = st.multiselect("Order", order_choices, default=[])

        family_avail = sorted(dat.loc[dat["order"].isin(order_sel), "family"].unique())
        family_sel = st.multiselect("Family", family_avail, default=family_avail)

        origin_avail = sorted(
            dat.loc[dat["order"].isin(order_sel) & dat["family"].isin(family_sel), "origin"].unique()
        )
        origin_sel = st.multiselect("Origin", origin_avail, default=origin_avail)

        preservation_avail = sorted(
            dat.loc[
                dat["order"].isin(order_sel)
                & dat["family"].isin(family_sel)
                & dat["origin"].isin(origin_sel),
                "preservation",
            ].unique()
        )
        preservation_sel = st.multiselect("Material type", preservation_avail, default=preservation_avail)

    with results_col:
        if not order_sel or not family_sel or not origin_sel or not preservation_sel:
            st.markdown(
                "<div style='text-align:center;'><p>To display data, make a selection using the "
                "filters on the left.</p></div>",
                unsafe_allow_html=True,
            )
        else:
            filtered = dat[
                dat["order"].isin(order_sel)
                & dat["family"].isin(family_sel)
                & dat["origin"].isin(origin_sel)
                & dat["preservation"].isin(preservation_sel)
            ].copy()

            family_order = ["All families"] + sorted(f for f in filtered["family"].unique() if f != "All families")
            filtered["family"] = pd.Categorical(filtered["family"], categories=family_order, ordered=True)
            filtered = filtered.sort_values(["family", "origin", "preservation"])

            display = filtered[
                ["order", "family", "preservation", "origin", "inventory", "digitised", "proportion"]
            ].copy()
            display["proportion"] = (display["proportion"] * 100).round(0).astype(int).astype(str) + "%"
            display.columns = [
                "Order",
                "Family",
                "Material type",
                "Origin",
                "Total specimens",
                "Digitised specimens",
                "Proportion digitised",
            ]
            st.dataframe(display, hide_index=True, width='stretch', height=550)


# ---- Tab: Names database -----------------------------------------------------

elif active_section == "Names database":
    st.subheader("NZ Arthropod Names Database")
    st.markdown(
        "Accepted names and synonymy for New Zealand arthropod taxa. Names are "
        "curated by NZAC staff as nomenclature changes in the literature."
    )

    try:
        names_df = load_names()
        names_error = None
    except Exception as exc:  # noqa: BLE001 - table may not exist yet
        names_df = NAMES_EMPTY_DF.copy()
        names_error = str(exc)

    if names_error:
        st.warning(
            f"Couldn't load the names table ({names_error}). "
            "Has supabase/schema.sql been run yet in the Supabase project?"
        )

    filt_col, view_col = st.columns([1, 3])

    with filt_col:
        order_opts = sorted(names_df["order_name"].dropna().unique())
        order_sel = st.multiselect("Order", order_opts, default=order_opts, key="names_order_filter")

        family_opts = sorted(
            names_df.loc[names_df["order_name"].isin(order_sel), "family"].dropna().unique()
        )
        family_sel = st.multiselect("Family", family_opts, default=family_opts, key="names_family_filter")

        accepted_sel = st.multiselect(
            "Accepted status", ["Accepted", "Synonym"], default=["Accepted", "Synonym"], key="names_accepted_filter"
        )
        search = st.text_input("Search name (scientific or common)", key="names_search")

    with view_col:
        view = names_df[names_df["order_name"].isin(order_sel) & names_df["family"].isin(family_sel)].copy()
        if not view.empty:
            status = view["is_accepted"].map(lambda v: "Accepted" if v else "Synonym")
            view = view[status.isin(accepted_sel)]
        if search and not view.empty:
            needle = search.lower()
            haystack = (view["part_name"].fillna("") + " " + view["common_name"].fillna("")).str.lower()
            view = view[haystack.str.contains(needle)]

        display = view.rename(columns=dict(NAMES_PUBLIC_COLUMNS))
        display = display[[label for _, label in NAMES_PUBLIC_COLUMNS if label in display.columns]]
        display = display.fillna("")
        st.dataframe(display, hide_index=True, width="stretch", height=500)

    st.divider()

    authenticator = get_authenticator()
    if authenticator is None:
        st.info("Editor login isn't configured yet for this tab — only viewing is available.")
    else:
        authenticator.login(location="main", key="names_login")
        editor_name = st.session_state.get("name")
        auth_status = st.session_state.get("authentication_status")

        if auth_status is False:
            st.error("Username or password is incorrect.")
        elif auth_status is None:
            st.info("Log in above if you have permission to add or update names.")
        elif auth_status:
            authenticator.logout("Log out", location="main", key="names_logout")
            st.success(f"Logged in as {editor_name}")

            # Deliberately st.radio rather than a nested st.tabs(): Streamlit tracks
            # tab selection by element position on the frontend, not real state, so
            # a rerun triggered by a widget inside a nested tab (a checkbox, a file
            # upload, ...) can desync it and make the OUTER tabs (Summary/Maps/etc.)
            # jump to the wrong one. st.radio with a key uses real session state and
            # doesn't have this problem.
            editor_section = st.radio(
                "Editor action",
                ["Add / update a name", "Bulk upload new names", "Bulk edit a group"],
                key="names_editor_section",
                horizontal=True,
                label_visibility="collapsed",
            )
            st.divider()

            # ---- Add / update a single name ----
            if editor_section == "Add / update a name":
                entry_type = st.radio(
                    "Type of entry",
                    ["New name", "Update to existing name"],
                    key="names_entry_type",
                    help="What type of entry is this: a brand new name, or a change to a name already in the database?",
                )

                existing = {}
                linked_name = None
                if entry_type == "Update to existing name":
                    part_names = sorted(names_df["part_name"].dropna().unique())
                    linked_name = st.selectbox(
                        "Name to update",
                        part_names,
                        index=None,
                        placeholder="Select the existing name to update",
                        key="names_linked_name",
                        help="The existing name that needs to be updated.",
                    )
                    if linked_name:
                        existing = names_df.loc[names_df["part_name"] == linked_name].iloc[0].to_dict()

                with st.form("names_form"):
                    st.caption("Fields marked * are required.")

                    st.markdown("**Identity**")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        genus = st.text_input(
                            "Genus*", value=_s(existing.get("genus")),
                            help="Enter Genus (capitalise first letter).",
                        )
                        subgenus = st.text_input("Subgenus", value=_s(existing.get("subgenus")))
                    with c2:
                        species = st.text_input(
                            "Species",
                            value=_s(existing.get("species")),
                            help="Species epithet only (add subspecies epithet after it if relevant). "
                            "Leave blank for genus-rank names. Do not add authority, tag names, "
                            "'sp.', or abbreviations.",
                        )
                        taxon_rank = st.selectbox(
                            "Taxon rank*",
                            TAXON_RANKS,
                            index=TAXON_RANKS.index(existing["taxon_rank"])
                            if existing.get("taxon_rank") in TAXON_RANKS
                            else 0,
                        )
                    with c3:
                        authors = st.text_input(
                            "Authors*",
                            value=_s(existing.get("authors")),
                            help="LAST name of author(s) only; no initials, year, or brackets.",
                        )
                        year_of_publication = st.text_input(
                            "Year of publication*",
                            value=_s(existing.get("year_of_publication")),
                            help="4-digit year.",
                        )

                    st.markdown("**Nomenclatural status**")
                    c4, c5 = st.columns(2)
                    with c4:
                        is_accepted = st.selectbox(
                            "Is accepted name?*",
                            YES_NO,
                            index=YES_NO.index("yes" if existing.get("is_accepted", True) else "no"),
                        )
                        accepted_name = st.text_input(
                            "Accepted name (required if not accepted)",
                            value=_s(existing.get("accepted_name")),
                        )
                    with c5:
                        is_original = st.selectbox(
                            "Is original combination (basionym)?*",
                            YES_NO,
                            index=YES_NO.index("yes" if existing.get("is_original", True) else "no"),
                        )
                        original_name = st.text_input(
                            "Original name (required if not original)",
                            value=_s(existing.get("original_name")),
                        )

                    st.markdown("**Classification**")
                    c6, c7, c8 = st.columns(3)
                    with c6:
                        class_ = st.text_input("Class*", value=_s(existing.get("class")))
                        subfamily = st.text_input("Subfamily", value=_s(existing.get("subfamily")))
                    with c7:
                        order_name_val = st.text_input("Order*", value=_s(existing.get("order_name")))
                        tribe = st.text_input("Tribe", value=_s(existing.get("tribe")))
                    with c8:
                        family = st.text_input("Family*", value=_s(existing.get("family")))
                        superfamily = st.text_input("Superfamily", value=_s(existing.get("superfamily")))

                    st.markdown("**Distribution & status**")
                    c9, c10, c11 = st.columns(3)
                    with c9:
                        origin = st.selectbox(
                            "Origin*",
                            ORIGIN_OPTIONS,
                            index=ORIGIN_OPTIONS.index(existing["origin"])
                            if existing.get("origin") in ORIGIN_OPTIONS
                            else 0,
                            help="Endemic = only in NZ; Indigenous = native to NZ but also elsewhere; "
                            "Exotic = accidental or deliberate introduction (e.g. biocontrol).",
                        )
                    with c10:
                        occurrence = st.selectbox(
                            "Occurrence*",
                            OCCURRENCE_OPTIONS,
                            index=OCCURRENCE_OPTIONS.index(existing["occurrence"])
                            if existing.get("occurrence") in OCCURRENCE_OPTIONS
                            else 0,
                        )
                    with c11:
                        doc_threat_status = st.text_input(
                            "DOC threat status", value=_s(existing.get("doc_threat_status"))
                        )
                    common_name = st.text_input(
                        "Common name(s)",
                        value=_s(existing.get("common_name")),
                        help="If more than one, separate with a semicolon.",
                    )

                    st.markdown("**Notes & reference**")
                    taxonomic_notes = st.text_area(
                        "Taxonomic notes",
                        value=_s(existing.get("taxonomic_notes")),
                        help="Any comment to clarify taxonomic status, or a tag name (e.g. spA).",
                    )
                    c12, c13 = st.columns(2)
                    with c12:
                        name_variation = st.text_input(
                            "Name variation", value=_s(existing.get("name_variation"))
                        )
                    with c13:
                        page = st.text_input(
                            "Page", value=_s(existing.get("page")),
                            help="First page of taxonomic description.",
                        )
                    primary_reference = st.text_area(
                        "Primary reference",
                        value=_s(existing.get("primary_reference")),
                        help="Citation with author(s), year, title, journal etc.",
                    )

                    submitted = st.form_submit_button("Save", width="stretch")

                if submitted:
                    if entry_type == "Update to existing name" and not linked_name:
                        st.error("Select the existing name to update.")
                    else:
                        record, errors = validate_and_build_record(
                            {
                                "genus": genus, "species": species, "authors": authors,
                                "year_of_publication": year_of_publication, "taxon_rank": taxon_rank,
                                "is_accepted": is_accepted, "accepted_name": accepted_name,
                                "is_original": is_original, "original_name": original_name,
                                "class": class_, "order_name": order_name_val, "superfamily": superfamily,
                                "family": family, "subfamily": subfamily, "tribe": tribe,
                                "subgenus": subgenus, "common_name": common_name, "origin": origin,
                                "occurrence": occurrence, "doc_threat_status": doc_threat_status,
                                "taxonomic_notes": taxonomic_notes, "name_variation": name_variation,
                                "page": page, "primary_reference": primary_reference,
                            }
                        )
                        if errors:
                            for error in errors:
                                st.error(error)
                        else:
                            now = datetime.now(timezone.utc).isoformat()
                            record["updated_by"] = editor_name
                            record["updated_at"] = now

                            client = get_supabase_client()
                            try:
                                if entry_type == "Update to existing name":
                                    client.table(NAMES_TABLE).update(record).eq("part_name", linked_name).execute()
                                    st.success(f"Updated '{linked_name}'.")
                                else:
                                    record["created_by"] = editor_name
                                    record["created_at"] = now
                                    client.table(NAMES_TABLE).insert(record).execute()
                                    st.success(f"Added '{record['part_name']}'.")
                                load_names.clear()
                                st.rerun()
                            except Exception as exc:  # noqa: BLE001 - surface any DB error to the editor
                                st.error(f"Could not save: {exc}")

            # ---- Bulk upload new names ----
            elif editor_section == "Bulk upload new names":
                st.caption(
                    "For when a batch of new names is published at once. Download the template, "
                    "fill in one row per new name, then upload it here. This only adds new names "
                    "— to change existing ones, use 'Add / update a name' or 'Bulk rename a group'."
                )
                st.download_button(
                    "Download template (.xlsx)",
                    data=build_names_template_xlsx(),
                    file_name="nzac_names_upload_template.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="bulk_template_download",
                )

                # Streamlit file_uploaders keep their file across reruns unless the
                # widget's key changes -- bump this counter after a successful
                # upload so the file is cleared instead of being re-parsed (and
                # re-validated as "already exists") against the data it just added.
                st.session_state.setdefault("bulk_upload_uploader_version", 0)
                uploaded = st.file_uploader(
                    "Upload completed file",
                    type=["xlsx", "csv"],
                    key=f"bulk_upload_file_{st.session_state.bulk_upload_uploader_version}",
                )

                if uploaded is not None:
                    try:
                        raw = parse_bulk_upload(uploaded)
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Could not read file: {exc}")
                        raw = None

                    if raw is not None:
                        template_headers = [label for _, label in BULK_TEMPLATE_COLUMNS]
                        missing_cols = [c for c in template_headers if c not in raw.columns]
                        if missing_cols:
                            st.error(
                                f"Missing expected column(s): {', '.join(missing_cols)}. "
                                "Please use the downloaded template."
                            )
                        else:
                            existing_part_names = set(names_df["part_name"].dropna())
                            records, row_errors, seen_in_batch = [], [], {}

                            for i, row in raw.iterrows():
                                excel_row = i + 2  # header is row 1
                                fields = {db_col: row[label] for db_col, label in BULK_TEMPLATE_COLUMNS}
                                if not any(str(v).strip() for v in fields.values()):
                                    continue  # skip blank rows

                                record, errors = validate_and_build_record(fields)
                                if record is not None:
                                    pn = record["part_name"]
                                    if pn in existing_part_names:
                                        errors.append(f"'{pn}' already exists — use Update instead.")
                                    if pn in seen_in_batch:
                                        errors.append(f"'{pn}' also appears in row {seen_in_batch[pn]}.")
                                    else:
                                        seen_in_batch[pn] = excel_row

                                if errors:
                                    row_errors.append((excel_row, errors))
                                else:
                                    records.append(record)

                            if row_errors:
                                st.error(f"{len(row_errors)} row(s) need fixing before uploading:")
                                for row_num, errs in row_errors:
                                    st.markdown(f"- **Row {row_num}:** " + "; ".join(errs))
                            elif not records:
                                st.warning("No data rows found in the uploaded file.")
                            else:
                                st.success(f"{len(records)} new name(s) ready to add.")
                                preview = pd.DataFrame(records)[["part_name", "full_name", "family", "origin"]]
                                preview.columns = ["PartName", "FullName", "Family", "Origin"]
                                st.dataframe(preview, hide_index=True, width="stretch", height=300)

                                confirm_bulk = st.checkbox(
                                    f"I've reviewed these {len(records)} name(s) and want to add them.",
                                    key="bulk_confirm",
                                )
                                if st.button("Add these names", disabled=not confirm_bulk, key="bulk_submit"):
                                    now = datetime.now(timezone.utc).isoformat()
                                    for r in records:
                                        r.update(created_by=editor_name, created_at=now,
                                                  updated_by=editor_name, updated_at=now)
                                    try:
                                        get_supabase_client().table(NAMES_TABLE).insert(records).execute()
                                        st.success(f"Added {len(records)} new name(s).")
                                        load_names.clear()
                                        st.session_state.bulk_upload_uploader_version += 1
                                        st.rerun()
                                    except Exception as exc:  # noqa: BLE001
                                        st.error(f"Could not save: {exc}")

            # ---- Bulk edit a group of records ----
            elif editor_section == "Bulk edit a group":
                st.caption(
                    "Change one or more fields across many records in one go — e.g. move every "
                    "species to a new genus after a generic transfer, or add publication details "
                    "(Authors, Year, Primary reference, Page...) to a batch of names from the same "
                    "paper. Note: this does not update free-text mentions in AcceptedName, "
                    "OriginalName, or Taxonomic notes on other records — check those separately."
                )

                st.markdown("**1. Select the records to edit**")
                select_mode = st.radio(
                    "How to select records",
                    ["By matching field value", "By choosing specific names"],
                    key="bulk_edit_select_mode",
                    horizontal=True,
                    label_visibility="collapsed",
                )

                if select_mode == "By matching field value":
                    match_labels = [label for _, label in RENAME_FIELDS]
                    match_label = st.selectbox("Field to match on", match_labels, key="bulk_edit_match_field")
                    match_field = dict((label, col) for col, label in RENAME_FIELDS)[match_label]

                    match_values = sorted(names_df[match_field].dropna().unique()) if not names_df.empty else []
                    match_value = st.selectbox(
                        f"Current {match_label}",
                        match_values,
                        index=None,
                        placeholder=f"Select the {match_label.lower()} to match",
                        key="bulk_edit_match_value",
                    )
                    affected = names_df[names_df[match_field] == match_value] if match_value else NAMES_EMPTY_DF
                else:
                    part_names = sorted(names_df["part_name"].dropna().unique()) if not names_df.empty else []
                    chosen_names = st.multiselect("Names to edit", part_names, key="bulk_edit_chosen_names")
                    affected = names_df[names_df["part_name"].isin(chosen_names)]

                if not affected.empty:
                    st.write(f"**{len(affected)}** record(s) selected.")
                    preview = affected[["part_name", "full_name"]].rename(
                        columns={"part_name": "PartName", "full_name": "FullName"}
                    )
                    st.dataframe(preview, hide_index=True, width="stretch", height=200)

                    st.markdown("**2. Choose what to change**")
                    field_labels = [label for _, label, *_ in BULK_EDITABLE_FIELDS]
                    chosen_field_labels = st.multiselect(
                        "Fields to bulk-set on all selected records", field_labels, key="bulk_edit_fields"
                    )
                    label_to_spec = {label: (db_col, kind, opts[0] if opts else None)
                                      for db_col, label, kind, *opts in BULK_EDITABLE_FIELDS}

                    new_values = {}
                    for label in chosen_field_labels:
                        db_col, kind, options = label_to_spec[label]
                        if kind == "select":
                            new_values[db_col] = st.selectbox(f"New {label}", options, key=f"bulk_edit_val_{db_col}")
                        else:
                            new_values[db_col] = st.text_input(f"New {label}", key=f"bulk_edit_val_{db_col}")

                    st.markdown("**3. Apply**")
                    edit_errors = []
                    if new_values.get("year_of_publication") and not (
                        new_values["year_of_publication"].isdigit()
                        and len(new_values["year_of_publication"]) == 4
                    ):
                        edit_errors.append("Year of publication must be a 4-digit number.")
                    for label in chosen_field_labels:
                        db_col, _kind, _opts = label_to_spec[label]
                        if db_col in ("genus", "authors", "class", "order_name", "family") and not new_values.get(db_col):
                            edit_errors.append(f"New {label} can't be blank.")

                    for error in edit_errors:
                        st.error(error)

                    confirm_edit = st.checkbox(
                        f"I understand this will update {len(affected)} record(s).", key="bulk_edit_confirm"
                    )
                    if st.button(
                        "Apply bulk edit",
                        disabled=not (chosen_field_labels and not edit_errors and confirm_edit),
                        key="bulk_edit_submit",
                    ):
                        now = datetime.now(timezone.utc).isoformat()
                        client = get_supabase_client()
                        apply_errors = []
                        for _, row in affected.iterrows():
                            update = dict(new_values)
                            if "year_of_publication" in update:
                                update["year_of_publication"] = int(update["year_of_publication"])
                            update["updated_by"] = editor_name
                            update["updated_at"] = now

                            if BULK_EDIT_DERIVED_TRIGGERS & set(new_values.keys()):
                                merged_genus = new_values.get("genus", row.get("genus"))
                                merged_species = _s(row.get("species"))
                                merged_authors = new_values.get("authors", row.get("authors"))
                                merged_year = str(new_values.get(
                                    "year_of_publication", row.get("year_of_publication")
                                ))
                                merged_is_original = new_values.get(
                                    "is_original", "yes" if row.get("is_original") else "no"
                                )
                                part_name, authority_and_year, full_name = compute_derived_fields(
                                    merged_genus, merged_species, merged_authors, merged_year, merged_is_original
                                )
                                update["part_name"] = part_name
                                update["authority_and_year"] = authority_and_year
                                update["full_name"] = full_name

                            try:
                                client.table(NAMES_TABLE).update(update).eq("id", row["id"]).execute()
                            except Exception as exc:  # noqa: BLE001
                                apply_errors.append(f"{row['part_name']}: {exc}")

                        if apply_errors:
                            st.error("Some records failed to update:\n" + "\n".join(apply_errors))
                        else:
                            st.success(f"Updated {len(affected)} record(s).")
                        load_names.clear()
                        st.rerun()


# ---- Tab: Maps ---------------------------------------------------------------

elif active_section == "Maps":
    n_points = round(len(loc), -1)
    st.markdown(
        f"The map below shows the localities of the approximately {n_points:,} georeferenced "
        "specimens in the NZAC. New georeferences are updated periodically."
    )

    loc_map = loc.dropna(subset=["decimal_lat", "decimal_long"])

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=loc_map,
        get_position="[decimal_long, decimal_lat]",
        get_fill_color="[255, 0, 0, 140]",
        get_radius=8000,
        pickable=True,
        radius_min_pixels=2,
        radius_max_pixels=20,
    )

    view_state = pdk.ViewState(latitude=-45, longitude=175, zoom=3)

    tooltip = {
        "html": "<b>{spp_name}</b><br/>{accession_number}<br/>{country}<br/>"
        "{geodetic_datum}<br/>{decimal_lat}, {decimal_long}",
        "style": {"backgroundColor": "#ffffff", "color": "#262730"},
    }

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_style="light",
        tooltip=tooltip,
    )
    st.pydeck_chart(deck, width='stretch', height=600)
