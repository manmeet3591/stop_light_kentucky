import streamlit as st
import pandas as pd
import geopandas as gpd
import numpy as np
import pydeck as pdk

# -----------------------------
# CONFIG
# -----------------------------
st.set_page_config(page_title="Kentucky Disaster Threat Map", layout="wide")

st.title("Kentucky Counties – Disaster Threat Levels")

st.markdown(
    """
This demo app assigns **random threat scores** to each Kentucky county and colors them
based on the threat level.

Color legend:
- **Green** – Low
- **White** – Moderate
- **Red** – High
- **Maroon** – Extreme
"""
)

# -----------------------------
# LOAD KENTUCKY COUNTIES GEOJSON
# -----------------------------
@st.cache_data
def load_counties():
    # Public Census TIGER/Line 2018 counties shapefile for whole US
    # We download once and filter Kentucky (STATEFP = '21')
    url = (
        "https://www2.census.gov/geo/tiger/TIGER2018/COUNTY/tl_2018_us_county.zip"
    )

    gdf = gpd.read_file(url)
    # Kentucky FIPS state code is 21
    ky = gdf[gdf["STATEFP"] == "21"].copy()
    ky = ky.to_crs(epsg=4326)  # ensure WGS84 lat/lon
    return ky


counties_gdf = load_counties()

# -----------------------------
# CREATE RANDOM THREAT SCORES
# -----------------------------
np.random.seed(42)  # for reproducibility

# Create a dataframe with random scores
threat_df = pd.DataFrame(
    {
        "GEOID": counties_gdf["GEOID"],
        "NAME": counties_gdf["NAME"],
        "threat_score": np.random.rand(len(counties_gdf)),  # 0–1
    }
)

# Map numeric score to discrete levels
def score_to_level(score: float) -> str:
    if score < 0.25:
        return "Low"
    elif score < 0.5:
        return "Moderate"
    elif score < 0.75:
        return "High"
    else:
        return "Extreme"


threat_df["threat_level"] = threat_df["threat_score"].apply(score_to_level)

# Map levels to colors (R, G, B)
COLOR_MAP = {
    "Low": [0, 128, 0],       # Green
    "Moderate": [255, 255, 255],  # White
    "High": [255, 0, 0],      # Red
    "Extreme": [128, 0, 0],   # Maroon
}

threat_df["color"] = threat_df["threat_level"].map(COLOR_MAP)

# Merge with geometry
counties_merged = counties_gdf.merge(threat_df, on=["GEOID", "NAME"])

# Explode multipolygons to polygons for pydeck
counties_merged = counties_merged.explode(ignore_index=True)

# -----------------------------
# CONTROL PANEL
# -----------------------------
with st.sidebar:
    st.header("Filters")

    level_filter = st.multiselect(
        "Threat levels to display",
        options=["Low", "Moderate", "High", "Extreme"],
        default=["Low", "Moderate", "High", "Extreme"],
    )

    show_table = st.checkbox("Show data table", value=True)

filtered = counties_merged[counties_merged["threat_level"].isin(level_filter)]

# -----------------------------
# PREPARE DATA FOR PYDECK
# -----------------------------
# pydeck expects coordinates as [ [lon, lat], [lon, lat], ... ]
def geometry_to_coordinates(geom):
    if geom.geom_type == "Polygon":
        return [list(geom.exterior.coords)]
    elif geom.geom_type == "MultiPolygon":
        return [list(poly.exterior.coords) for poly in geom.geoms]
    else:
        return []


filtered = filtered.copy()
filtered["coordinates"] = filtered["geometry"].apply(geometry_to_coordinates)

# Compute map center
center_lon = filtered.geometry.centroid.x.mean()
center_lat = filtered.geometry.centroid.y.mean()

# Build the PyDeck layer
polygon_layer = pdk.Layer(
    "PolygonLayer",
    data=filtered,
    get_polygon="coordinates",
    get_fill_color="color",
    get_line_color=[0, 0, 0],
    line_width_min_pixels=1,
    pickable=True,
    auto_highlight=True,
)

view_state = pdk.ViewState(
    longitude=center_lon,
    latitude=center_lat,
    zoom=6,
    pitch=0,
)

r = pdk.Deck(
    layers=[polygon_layer],
    initial_view_state=view_state,
    tooltip={
        "html": "<b>{NAME} County</b><br/>Threat: {threat_level}<br/>Score: {threat_score}",
        "style": {"color": "black"},
    },
)

# -----------------------------
# LAYOUT
# -----------------------------
col1, col2 = st.columns([2, 1])

with col1:
    st.pydeck_chart(r)

with col2:
    st.subheader("Threat Summary")
    counts = (
        threat_df.groupby("threat_level")
        .size()
        .reindex(["Low", "Moderate", "High", "Extreme"])
        .fillna(0)
        .astype(int)
    )
    st.bar_chart(counts)

    if show_table:
        st.subheader("County Threat Data")
        st.dataframe(
            threat_df[["NAME", "threat_level", "threat_score"]]
            .sort_values("threat_score", ascending=False)
            .reset_index(drop=True)
        )

st.caption(
    "Note: Scores are randomly generated on each run. "
    "In a real app, you would replace them with real disaster risk data."
)
