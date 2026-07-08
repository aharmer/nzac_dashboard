"""NZAC Project Dashboard — Streamlit port of the original R/Shiny app."""

import base64
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

APP_NAME = "NZAC Project Dashboard"
APP_VER = "2.0"
GITHUB_LINK = "https://github.com/aharmer/nzac_dashboard"
ACCENT = "#3f9c82"

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"

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

tab_summary, tab_projects, tab_taxa, tab_maps = st.tabs(
    ["Summary", "Digitisation projects", "View progress by taxa", "Maps"]
)


# ---- Tab: Summary -----------------------------------------------------------

with tab_summary:
    total_dig = int(dat.loc[dat["origin"] == "All", "digitised"].sum())
    total_inv = int(dat.loc[dat["origin"] == "All", "inventory"].sum())
    pct_dig = round(total_dig / total_inv * 100)
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
        "The intent of this site is to show progress and projects that are part of "
        "the digitisation program in the NZAC."
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
        st.plotly_chart(fig, use_container_width=True)

    with table_col:
        st.dataframe(summary_tab, hide_index=True, use_container_width=True, height=200)

    st.markdown(
        'Created and maintained by <a href="https://www.landcareresearch.co.nz/about-us/our-people/aaron-harmer" '
        'target="_blank">Dr Aaron Harmer</a>.',
        unsafe_allow_html=True,
    )


# ---- Tab: Digitisation projects ---------------------------------------------

with tab_projects:
    img_col, text_col = st.columns([2, 3])
    with img_col:
        st.image(str(ASSETS_DIR / "rapiid_lite.png"), width=350)
    with text_col:
        st.markdown(
            "Digitising biological collections is essential for research and conservation "
            "but remains slow and expensive, particularly for pinned insect specimens with "
            "tiny, stacked labels. Current manual transcription methods in Australia and New "
            "Zealand create a decadal bottleneck, while existing automated systems are costly "
            "and space-intensive. We developed RAPIIDlite (RAked Pinned Insect Imaging Device), "
            "a modular, semi-automated imaging system and associated processing pipeline that "
            "dramatically accelerates specimen digitisation. The system combines customisable "
            "hardware with user-friendly Python software and advanced machine learning. Images "
            "are processed through GoogleVision OCR and spaCy natural language processing to "
            "automatically extract and parse label data into standardised Darwin Core database "
            "fields. Testing shows RAPIIDlite significantly speeds digitisation while improving "
            "standardisation and reducing errors."
        )


# ---- Tab: View progress by taxa ---------------------------------------------

with tab_taxa:
    st.info(
        "There are four filters to access information: taxonomic order, family, origin, and "
        "material type. The five 'mega-diverse' insect orders (Coleoptera, Diptera, Hemiptera, "
        "Hymenoptera, Lepidoptera) have information at the family level. Information is not yet "
        "available at the family level for other taxonomic orders, or for specimens stored in "
        "fluid or on microscope slides (this information is presented only at the order level). "
        "For non-insects, information is a mix at the level of Phyla, Class, or Order."
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
            st.dataframe(display, hide_index=True, use_container_width=True, height=550)


# ---- Tab: Maps ---------------------------------------------------------------

with tab_maps:
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
    st.pydeck_chart(deck, use_container_width=True, height=600)
