import streamlit as st
import pandas as pd
import geopandas as gpd
import numpy as np
import pydeck as pdk

# -----------------------------
# CONFIG
# -----------------------------
st.set_page_config(page_title="Kentucky Hazard Maps", layout="wide")

st.title("Kentucky County Hazard Maps")

st.markdown(
    """
This app shows **7 maps** for Kentucky counties:

- **Overall Multi-Hazard map** using a stoplight scale (White / Green / Yellow / Red)
- **6 hazard-specific maps** with random scores, using hazard-representative color ramps:
  - Flooding – 3 shades of green
  - Winter Weather – 3 shades of blue
  - Wind – 3 shades of purple
  - Severe Weather – 3 shades of red
  - Extreme Temperature – blue (low) to orange (high)
  - Other – 3 shades of grayscale

All scores are **randomly generated** for demo purposes.
Replace them with real data as needed.
"""
)

# -----------------------------
# LOAD KENTUCKY COUNTIES GEO DATA
# -----------------------------
@st.cache_data
def load_counties():
    # Census TIGER/Line counties for US, then filter Kentucky (STATEFP = '21')
    url = "https://www2.census.gov/geo/tiger/TIGER2018/COUNTY/tl_2018_us_county.zip"
    gdf = gpd.read_file(url)
    ky = gdf[gdf["STATEFP"] == "21"].copy()
    ky = ky.to_crs(epsg=4326)  # WGS84 lat/lon
    ky = ky.explode(ignore_index=True)
    return ky


counties = load_counties()

# -----------------------------
# HAZARD DEFINITIONS
# -----------------------------
# 6 hazards for the 6 tabs
HAZARDS = [
    ("Flooding", "flood"),
    ("Winter Weather", "winter"),
    ("Wind", "wind"),
    ("Severe Weather", "severe"),
    ("Extreme Temperature", "extreme_temp"),
    ("Other", "other"),
]

# -----------------------------
# OVERALL STOPLIGHT SCALE (4 LEVELS)
# -----------------------------
def overall_score_to_level(score: float) -> str:
    if score < 0.25:
        return "Very Low (White)"
    elif score < 0.5:
        return "Low (Green)"
    elif score < 0.75:
        return "Elevated (Yellow)"
    else:
        return "High (Red)"


OVERALL_LEVELS_ORDER = [
    "Very Low (White)",
    "Low (Green)",
    "Elevated (Yellow)",
    "High (Red)",
]

OVERALL_COLOR_MAP = {
    "Very Low (White)": [255, 255, 255],  # White
    "Low (Green)": [0, 128, 0],           # Green
    "Elevated (Yellow)": [255, 255, 0],   # Yellow
    "High (Red)": [255, 0, 0],            # Red
}

# -----------------------------
# HAZARD-SPECIFIC LEVELS (3 LEVELS)
# -----------------------------
def hazard_score_to_level(score: float) -> str:
    """3-category scale: Low / Medium / High"""
    if score < 1/3:
        return "Low"
    elif score < 2/3:
        return "Medium"
    else:
        return "High"


HAZARD_LEVELS_ORDER = ["Low", "Medium", "High"]

# Color maps for each hazard
HAZARD_COLOR_MAPS = {
    # Flooding – three greens
    "flood": {
        "Low": [198, 239, 206],    # light green
        "Medium": [120, 200, 140], # medium green
        "High": [0, 100, 0],       # dark green
    },
    # Winter – three blues
    "winter": {
        "Low": [198, 219, 239],    # light blue
        "Medium": [91, 155, 213],  # medium blue
        "High": [0, 70, 140],      # dark blue
    },
    # Wind – three purples
    "wind": {
        "Low": [221, 214, 235],    # light purple
        "Medium": [165, 105, 189], # medium purple
        "High": [88, 24, 69],      # dark purple
    },
    # Severe Weather – three reds
    "severe": {
        "Low": [252, 199, 191],    # light red
        "Medium": [244, 96, 96],   # medium red
        "High": [153, 0, 0],       # dark red
    },
    # Extreme Temperature – blue (low) to orange (high)
    "extreme_temp": {
        "Low": [0, 112, 192],      # blue
        "Medium": [255, 192, 0],   # yellow-ish
        "High": [237, 125, 49],    # orange
    },
    # Other – grayscale
    "other": {
        "Low": [230, 230, 230],    # light gray
        "Medium": [160, 160, 160], # medium gray
        "High": [90, 90, 90],      # dark gray
    },
}

# -----------------------------
# RANDOM HAZARD SCORES PER COUNTY
# -----------------------------
np.random.seed(42)  # reproducible demo

# Generate hazard-specific scores, levels, colors
for label, key in HAZARDS:
    score_col = f"{key}_score"
    level_col = f"{key}_level"
    color_col = f"{key}_color"

    counties[score_col] = np.random.rand(len(counties))  # 0–1
    counties[level_col] = counties[score_col].apply(hazard_score_to_level)
    counties[color_col] = counties[level_col].map(HAZARD_COLOR_MAPS[key])

# Overall = average of all hazard scores
score_cols = [f"{key}_score" for _, key in HAZARDS]
counties["overall_score"] = counties[score_cols].mean(axis=1)
counties["overall_level"] = counties["overall_score"].apply(overall_score_to_level)
counties["overall_color"] = counties["overall_level"].map(OVERALL_COLOR_MAP)

# -----------------------------
# GEOMETRY -> COORDINATES FOR PYDECK
# -----------------------------
def geometry_to_coordinates(geom):
    if geom.geom_type == "Polygon":
        return [list(geom.exterior.coords)]
    elif geom.geom_type == "MultiPolygon":
        return [list(poly.exterior.coords) for poly in geom.geoms]
    else:
        return []


counties["coordinates"] = counties["geometry"].apply(geometry_to_coordinates)

# Map center
center_lon = counties.geometry.centroid.x.mean()
center_lat = counties.geometry.centroid.y.mean()

view_state = pdk.ViewState(
    longitude=center_lon,
    latitude=center_lat,
    zoom=6,
    pitch=0,
)

# -----------------------------
# HELPERS
# -----------------------------
def make_hazard_deck(df, level_col, score_col, color_col, hazard_label):
    layer = pdk.Layer(
        "PolygonLayer",
        data=df,
        get_polygon="coordinates",
        get_fill_color=color_col,  # column with [R,G,B]
        get_line_color=[0, 0, 0],
        line_width_min_pixels=1,
        pickable=True,
        auto_highlight=True,
    )

    tooltip_html = (
        "<b>{NAME} County</b><br/>"
        + f"{hazard_label} level: " + "{" + level_col + "}" + "<br/>"
        + "Score: " + "{" + score_col + "}"
    )

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip={"html": tooltip_html, "style": {"color": "black"}},
    )
    return deck


def plot_level_counts(df, level_col, order):
    counts = (
        df[level_col]
        .value_counts()
        .reindex(order)
        .fillna(0)
        .astype(int)
    )
    st.bar_chart(counts)


# -----------------------------
# SIDEBAR LEGEND
# -----------------------------
with st.sidebar:
    st.header("Legends")

    st.markdown("### Overall (Stoplight)")
    st.markdown(
        """
- **White** – Very Low
- **Green** – Low
- **Yellow** – Elevated
- **Red** – High
"""
    )

    st.markdown("### Hazard Color Ramps")
    st.markdown(
        """
- **Flooding** – 3 greens (light → dark)
- **Winter Weather** – 3 blues
- **Wind** – 3 purples
- **Severe Weather** – 3 reds
- **Extreme Temperature** – blue (low) → orange (high)
- **Other** – 3 grays (light → dark)

All values are random demo data.
"""
    )

# -----------------------------
# 7 TABS: OVERALL + 6 HAZARDS
# -----------------------------
tab_labels = ["Overall"] + [label for label, _ in HAZARDS]
tabs = st.tabs(tab_labels)

# ---- Overall tab ----
with tabs[0]:
    st.subheader("Overall Multi-Hazard Threat (Stoplight – White / Green / Yellow / Red)")

    col_map, col_stats = st.columns([2, 1])

    with col_map:
        deck = make_hazard_deck(
            counties, "overall_level", "overall_score", "overall_color", "Overall"
        )
        st.pydeck_chart(deck)

    with col_stats:
        st.markdown("**Overall Level Distribution**")
        plot_level_counts(counties, "overall_level", OVERALL_LEVELS_ORDER)

        st.markdown("**Sample Data (Top 20 Counties by Overall Score)**")
        st.dataframe(
            counties[["NAME", "overall_level", "overall_score"]]
            .drop_duplicates(subset=["NAME"])
            .sort_values("overall_score", ascending=False)
            .head(20)
            .reset_index(drop=True)
        )

# ---- Hazard-specific tabs ----
for i, (label, key) in enumerate(HAZARDS, start=1):
    score_col = f"{key}_score"
    level_col = f"{key}_level"
    color_col = f"{key}_color"

    with tabs[i]:
        st.subheader(f"{label} Hazard Map")

        col_map, col_stats = st.columns([2, 1])

        with col_map:
            deck = make_hazard_deck(
                counties, level_col, score_col, color_col, label
            )
            st.pydeck_chart(deck)

        with col_stats:
            st.markdown(f"**{label} Level Distribution**")
            plot_level_counts(counties, level_col, HAZARD_LEVELS_ORDER)

            st.markdown(f"**Sample Data (Top 20 Counties by {label} Score)**")
            st.dataframe(
                counties[["NAME", level_col, score_col]]
                .drop_duplicates(subset=["NAME"])
                .sort_values(score_col, ascending=False)
                .head(20)
                .reset_index(drop=True)
            )

st.caption(
    "Demo only – all hazard scores are random. Replace with real Kentucky flood, "
    "winter, wind, severe, extreme temperature, and other hazard data as needed."
)
