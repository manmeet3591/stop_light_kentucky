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
- **6 hazard-specific maps** with random scores:
  - Flood
  - Lightning
  - Tornado
  - Winter Weather
  - Severe Storm
  - Drought

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
HAZARDS = [
    ("Flood", "flood"),
    ("Lightning", "lightning"),
    ("Tornado", "tornado"),
    ("Winter Weather", "winter"),
    ("Severe Storm", "severe"),
    ("Drought", "drought"),
]

# Stoplight-style levels & colors
# 4 levels -> White, Green, Yellow, Red
def score_to_level(score: float) -> str:
    if score < 0.25:
        return "Very Low (White)"
    elif score < 0.5:
        return "Low (Green)"
    elif score < 0.75:
        return "Elevated (Yellow)"
    else:
        return "High (Red)"


COLOR_MAP = {
    "Very Low (White)": [255, 255, 255],  # White
    "Low (Green)": [0, 128, 0],           # Green
    "Elevated (Yellow)": [255, 255, 0],   # Yellow
    "High (Red)": [255, 0, 0],            # Red
}

# -----------------------------
# RANDOM HAZARD SCORES PER COUNTY
# -----------------------------
np.random.seed(42)  # reproducible demo

for label, key in HAZARDS:
    score_col = f"{key}_score"
    level_col = f"{key}_level"
    color_col = f"{key}_color"

    counties[score_col] = np.random.rand(len(counties))  # 0–1
    counties[level_col] = counties[score_col].apply(score_to_level)
    counties[color_col] = counties[level_col].map(COLOR_MAP)

# Overall = average of all hazard scores
score_cols = [f"{key}_score" for _, key in HAZARDS]
counties["overall_score"] = counties[score_cols].mean(axis=1)
counties["overall_level"] = counties["overall_score"].apply(score_to_level)
counties["overall_color"] = counties["overall_level"].map(COLOR_MAP)

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
# HELPER TO BUILD A MAP FOR ANY HAZARD
# -----------------------------
def make_hazard_deck(df, level_col, score_col, color_col, hazard_label):
    layer = pdk.Layer(
        "PolygonLayer",
        data=df,
        get_polygon="coordinates",
        get_fill_color=color_col,
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


def plot_level_counts(df, level_col):
    counts = (
        df[level_col]
        .value_counts()
        .reindex(
            ["Very Low (White)", "Low (Green)", "Elevated (Yellow)", "High (Red)"]
        )
        .fillna(0)
        .astype(int)
    )
    st.bar_chart(counts)


# -----------------------------
# SIDEBAR LEGEND
# -----------------------------
with st.sidebar:
    st.header("Legend – Stoplight Scale")
    st.markdown(
        """
- **White** – Very Low
- **Green** – Low
- **Yellow** – Elevated
- **Red** – High

All current values are random demo data.
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
        plot_level_counts(counties, "overall_level")
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
            plot_level_counts(counties, level_col)

            st.markdown(f"**Sample Data (Top 20 Counties by {label} Score)**")
            st.dataframe(
                counties[["NAME", level_col, score_col]]
                .drop_duplicates(subset=["NAME"])
                .sort_values(score_col, ascending=False)
                .head(20)
                .reset_index(drop=True)
            )

st.caption(
    "Demo only – all hazard scores are random. Replace with real Kentucky Flood, "
    "Lightning, Tornado, Winter Weather, Severe Storm, and Drought data as needed."
)
