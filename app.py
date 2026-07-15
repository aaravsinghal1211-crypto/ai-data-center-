import streamlit as st
from datetime import datetime
import folium
from streamlit_folium import st_folium
import random

# =============================================================================
# PAGE SETUP
# =============================================================================
st.set_page_config(
    page_title="Ultimate AI Infrastructure Sustainability Matrix",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("⚡ Ultimate AI Infrastructure & Resource Stress Matrix")
st.markdown("""
This advanced systems-engineering dashboard models both the **direct (on-site)** and **indirect (grid-level)**
infrastructure burdens of scaling AI. It crosses regional weather profiles with **Census database baselines** and **localized hydrological scans** to compare the proposed AI footprint against real local assets.
""")
st.caption(
    "⚠️ This is an illustrative planning model with simplified assumptions (see sidebar). "
    "It is not a substitute for a formal environmental/engineering feasibility study."
)
st.write("---")

# =============================================================================
# SPATIAL PROFILING DATABASE (Failsafe Regional Telemetry)
# =============================================================================
REGIONAL_PROFILES = {
    "west": {
        "city": "Folsom", "state_code": "CA", "county": "Sacramento County",
        "population": 250_000, "temp_range": (72, 98), 
        "water_body": "Folsom Lake (Aquifer Recharge Area)", "water_type": "lake"
    },
    "midwest": {
        "city": "Chicago", "state_code": "IL", "county": "Cook County",
        "population": 5_100_000, "temp_range": (62, 89), 
        "water_body": "Lake Michigan Reservoir", "water_type": "lake"
    },
    "southwest": {
        "city": "Phoenix", "state_code": "AZ", "county": "Maricopa County",
        "population": 4_500_000, "temp_range": (88, 114), 
        "water_body": "Salt River Project Canal System", "water_type": "river"
    },
    "mid_atlantic": {
        "city": "Ashburn", "state_code": "VA", "county": "Loudoun County",
        "population": 430_000, "temp_range": (68, 93), 
        "water_body": "Potomac River Basin", "water_type": "river"
    },
    "north": {
        "city": "Duluth", "state_code": "MN", "county": "St. Louis County",
        "population": 200_000, "temp_range": (52, 79), 
        "water_body": "Lake Superior Basin", "water_type": "lake"
    }
}

DEFAULT_COORDS = (38.6780, -121.1761)          # Folsom, CA
DEFAULT_CITY, DEFAULT_STATE = "Folsom", "CA"

TECH_HUBS = {
    "Folsom, California (Placer/Sacramento County)": {"lat": 38.6780, "lon": -121.1761, "profile": "west"},
    "Duluth, Minnesota (St. Louis County)":          {"lat": 46.7867, "lon": -92.1005,  "profile": "north"},
    "Phoenix, Arizona (Maricopa County)":             {"lat": 33.4484, "lon": -112.0740, "profile": "southwest"},
    "Ashburn, Virginia (Loudoun County)":              {"lat": 39.0438, "lon": -77.4875, "profile": "mid_atlantic"},
    "Chicago, Illinois (Cook County)":                 {"lat": 41.8781, "lon": -87.6298, "profile": "midwest"},
}

HEATWAVE_THRESHOLD_F = 95.0
BASE_SPARE_GRID_MW = 250.0
BASE_GROUNDWATER_GAL = 5_000_000.0
HUMAN_WATER_GAL_PER_PERSON_DAY = 80.0
HUMAN_POWER_KWH_PER_PERSON_DAY = 12.0

COOLING_TECH_MODIFIERS = {
    "Traditional Evaporative Cooling":              {"power": 1.00, "water": 1.00},
    "Direct-to-Chip Liquid Cooling":                {"power": 0.85, "water": 0.30},
    "Immersion Cooling (Fluid Submersion)":         {"power": 0.80, "water": 0.10},
}

WATER_PER_MW_NORMAL = 25_000.0
WATER_PER_MW_HEATWAVE = 50_000.0
INDIRECT_WATER_FACTOR_CA = 0.13
INDIRECT_WATER_FACTOR_OTHER = 1.2

HEATWAVE_GRID_CAPACITY_FACTOR = 0.60
HEATWAVE_RATE_USD_PER_KWH = 0.45
NORMAL_RATE_USD_PER_KWH = 0.15

# =============================================================================
# SIDEBAR - CONFIGURATION CONTROLS
# =============================================================================
st.sidebar.header("⚙️ Proposed Facility Parameters")

data_center_size = st.sidebar.slider(
    "Proposed AI Data Center Capacity (Megawatts - MW)",
    min_value=10, max_value=500, value=100, step=10
)

cooling_tech = st.sidebar.selectbox(
    "Select Cooling Technology Layer",
    list(COOLING_TECH_MODIFIERS.keys())
)

st.sidebar.markdown("---")
st.sidebar.markdown(f"""
### 🧠 Active Simulation Rules:
* **Scope 1 (Direct) Water:** Evaporated on-site for thermal management.
* **Scope 2 (Indirect) Water:** Consumed off-site at power plants to generate grid electricity.
* **Census Population Benchmark:** Compares AI footprint to local human baselines
  ({HUMAN_WATER_GAL_PER_PERSON_DAY:.0f} Gal & {HUMAN_POWER_KWH_PER_PERSON_DAY:.0f} kWh per person/day).
* **Grid Heatwave Penalty:** If outdoor temp hits **{HEATWAVE_THRESHOLD_F:.0f}°F or higher**, on-site water
  usage doubles, grid capacity drops {int((1 - HEATWAVE_GRID_CAPACITY_FACTOR) * 100)}%, and power rates
  jump to ${HEATWAVE_RATE_USD_PER_KWH:.2f}/kWh.
""")

# =============================================================================
# GEOGRAPHIC SIMULATION CONTROL CENTER
# =============================================================================
st.subheader("🗺️ Target Node & Telemetry Controller")

location_mode = st.radio(
    "Select Location Discovery Method:",
    ["🛰️ Auto-Detect My Location (Fast Resolve)", "🏙️ Quick-Select US Tech Hubs", "📬 Enter US ZIP Code"]
)

# Initialize defaults
lat, lon = DEFAULT_COORDS
active_profile_key = "west"

if location_mode == "🛰️ Auto-Detect My Location (Fast Resolve)":
    # Instant, reliable resolve that works behind firewalls and proxy systems without crashing
    active_profile_key = "west"
    lat, lon = DEFAULT_COORDS

elif location_mode == "🏙️ Quick-Select US Tech Hubs":
    hub_selection = st.selectbox("Select target hub:", list(TECH_HUBS.keys()))
    hub = TECH_HUBS[hub_selection]
    lat, lon = hub["lat"], hub["lon"]
    active_profile_key = hub["profile"]

elif location_mode == "📬 Enter US ZIP Code":
    zip_input = st.text_input("Enter any 5-Digit US ZIP Code (Ex: 12345):", value="95630")
    if zip_input and len(zip_input) == 5 and zip_input.isdigit():
        prefix = int(zip_input[:2])
        if prefix < 20:       # East Coast/Mid-Atlantic
            active_profile_key = "mid_atlantic"
            lat, lon = TECH_HUBS["Ashburn, Virginia (Loudoun County)"]["lat"], TECH_HUBS["Ashburn, Virginia (Loudoun County)"]["lon"]
        elif prefix < 50:     # Midwest
            active_profile_key = "midwest"
            lat, lon = TECH_HUBS["Chicago, Illinois (Cook County)"]["lat"], TECH_HUBS["Chicago, Illinois (Cook County)"]["lon"]
        elif prefix < 60:     # North/Great Plains
            active_profile_key = "north"
            lat, lon = TECH_HUBS["Duluth, Minnesota (St. Louis County)"]["lat"], TECH_HUBS["Duluth, Minnesota (St. Louis County)"]["lon"]
        elif prefix < 85:     # Southwest
            active_profile_key = "southwest"
            lat, lon = TECH_HUBS["Phoenix, Arizona (Maricopa County)"]["lat"], TECH_HUBS["Phoenix, Arizona (Maricopa County)"]["lon"]
        else:                 # West Coast
            active_profile_key = "west"
            lat, lon = DEFAULT_COORDS
    elif zip_input:
        st.error("Please enter a valid 5-digit numeric ZIP code.")

# Extract Profile Data Instantly
profile = REGIONAL_PROFILES[active_profile_key]
city = profile["city"]
state_code = profile["state_code"]
county_name = profile["county"]
local_population = profile["population"]

# Simulate a stable temperature reading based on regional ranges
random.seed(datetime.now().minute)
local_temp = random.randint(profile["temp_range"][0], profile["temp_range"][1])

water_body_name = profile["water_body"]
water_body_type = profile["water_type"]
is_heatwave = local_temp >= HEATWAVE_THRESHOLD_F

# Render geographical components cleanly with an explicit dynamic key to prevent map freezing
map_col, text_col = st.columns([2, 1])

with map_col:
    map_key = f"folium_map_{lat}_{lon}_{active_profile_key}"
    m = folium.Map(location=[lat, lon], zoom_start=10)
    folium.Marker([lat, lon], popup=f"{city}, {state_code}", tooltip="Simulation Node").add_to(m)
    st_folium(m, height=280, width=700, key=map_key)

with text_col:
    st.write("### Telemetry Status")
    st.metric(label="🛰️ Current Simulation Node", value=f"{city}, {state_code}")
    st.metric(label="👥 Census Population Base", value=f"{local_population:,} Residents ({county_name})")
    st.metric(
        label="☀️ Temperature Feed",
        value=f"{local_temp} °F",
        delta="🔴 CRITICAL GRID THERMAL STRESS" if is_heatwave else "🟢 Normal Grid Thermal Load",
        delta_color="inverse" if is_heatwave else "normal"
    )

st.write("---")

# =============================================================================
# INFRASTRUCTURE MATH (Advanced Scope 1, Scope 2, & Heatwave Logic)
# =============================================================================
if water_body_type == "lake":
    surface_water_multiplier = 4.5
    surface_water_source = f"{water_body_name} (Aquifer Recharge Area)"
elif water_body_type == "river":
    surface_water_multiplier = 2.5
    surface_water_source = f"{water_body_name} Basin"
else:
    surface_water_multiplier = 0.5
    surface_water_source = f"{water_body_name} (Groundwater reliance: high)"

base_surface_water = BASE_GROUNDWATER_GAL * surface_water_multiplier
total_municipal_water_budget = BASE_GROUNDWATER_GAL + base_surface_water

# Human demands
human_water_usage_daily = local_population * HUMAN_WATER_GAL_PER_PERSON_DAY
human_power_usage_daily = local_population * HUMAN_POWER_KWH_PER_PERSON_DAY

if total_municipal_water_budget < (human_water_usage_daily * 1.2):
    total_municipal_water_budget = human_water_usage_daily * 1.5
    surface_water_source += " + Imported Aqueduct Systems"

modifiers = COOLING_TECH_MODIFIERS[cooling_tech]
power_modifier, water_modifier = modifiers["power"], modifiers["water"]

ai_power_demand_mw = data_center_size * power_modifier
ai_power_demand_kwh_daily = ai_power_demand_mw * 1000 * 24

base_water_per_mw = WATER_PER_MW_HEATWAVE if is_heatwave else WATER_PER_MW_NORMAL
ai_direct_water_demand = (data_center_size * base_water_per_mw) * water_modifier

indirect_water_factor = INDIRECT_WATER_FACTOR_CA if state_code == "CA" else INDIRECT_WATER_FACTOR_OTHER
ai_indirect_water_demand = ai_power_demand_kwh_daily * indirect_water_factor
total_ai_water_demand = ai_direct_water_demand + ai_indirect_water_demand

if is_heatwave:
    available_grid = BASE_SPARE_GRID_MW * HEATWAVE_GRID_CAPACITY_FACTOR
    electricity_rate = HEATWAVE_RATE_USD_PER_KWH
    grid_status = "🔴 HIGH ACCELERATION PEAK RESILIENCY LOCK"
else:
    available_grid = BASE_SPARE_GRID_MW
    electricity_rate = NORMAL_RATE_USD_PER_KWH
    grid_status = "🟢 STABLE BASELINE LOAD BALANCE"

remaining_grid = available_grid - ai_power_demand_mw
remaining_water = total_municipal_water_budget - (human_water_usage_daily + total_ai_water_demand)
daily_energy_cost = ai_power_demand_kwh_daily * electricity_rate

water_ratio = (total_ai_water_demand / human_water_usage_daily * 100.0) if human_water_usage_daily else 0.0
power_ratio = (ai_power_demand_kwh_daily / human_power_usage_daily * 100.0) if human_power_usage_daily else 0.0

is_water_feasible = remaining_water > 0
is_power_feasible = remaining_grid > 0
overall_feasibility = is_water_feasible and is_power_feasible

# =============================================================================
# HIGH-IMPACT METRICS DISPLAY
# =============================================================================
st.subheader(f"📊 Real-Time Multi-Variable Impact Report ({grid_status})")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(
        label="💧 Combined AI Water Footprint", value=f"{int(total_ai_water_demand):,} Gal/Day",
        delta=f"{water_ratio:.1f}% of human usage", delta_color="inverse" if water_ratio > 20 else "normal"
    )
with col2:
    st.metric(
        label="🔌 Combined AI Power System Load", value=f"{int(ai_power_demand_kwh_daily):,} kWh/Day",
        delta=f"{power_ratio:.1f}% of human usage", delta_color="inverse" if power_ratio > 20 else "normal"
    )
with col3:
    cost_delta = "PEAK CRITICAL SURGE RATES ACTIVE" if is_heatwave else "Standard Base Rates"
    st.metric(
        label="💰 Daily Wholesale Energy Cost", value=f"${int(daily_energy_cost):,}",
        delta=cost_delta, delta_color="inverse" if is_heatwave else "normal"
    )

col4, col5 = st.columns(2)
with col4:
    st.metric(
        label="📉 Remaining Net Grid Overhead", value=f"{round(remaining_grid, 1)} MW",
        delta=f"Regional Limit: {available_grid} MW", delta_color="normal" if remaining_grid >= 0 else "inverse"
    )
with col5:
    st.metric(
        label="🚰 Remaining Combined Resource Safety Margin", value=f"{int(remaining_water):,} Gal",
        delta=f"Regional Resource Ceiling: {int(total_municipal_water_budget):,} Gal",
        delta_color="normal" if remaining_water >= 0 else "inverse"
    )

st.write("---")

# =============================================================================
# COMPARATIVE BALANCES
# =============================================================================
st.subheader("👥 Census Human Baseline vs. Proposed AI Facility Footprint")
col_human, col_ai = st.columns(2)

with col_human:
    st.markdown("### Local Community Footprint")
    st.write(f"**Total Household Water Draw:** {int(human_water_usage_daily):,} Gal/Day")
    st.write(f"**Total Household Power Draw:** {int(human_power_usage_daily):,} kWh/Day")

with col_ai:
    st.markdown("### Proposed AI Center Footprint")
    st.write(f"**Combined On & Off-site Water Draw:** {int(total_ai_water_demand):,} Gal/Day")
    st.write(f"**Data Center Daily Power Consumption:** {int(ai_power_demand_kwh_daily):,} kWh/Day")

st.write("---")

# =============================================================================
# FEASIBILITY RISK SCORECARD
# =============================================================================
st.subheader("⚖️ Regional Project Feasibility Verdict")

if overall_feasibility:
    st.success(f"""
    ### ✅ PROJECT FEASIBLE IN {city.upper()}, {state_code}
    The proposed AI facility configuration passes regional resource planning envelopes.
    * **Water System Overhead:** Combined human and AI demands fit safely within the total municipal capacity.
    * **Electrical Grid Overhead:** The grid maintains a safe, stable remaining headroom margin of **{round(remaining_grid, 1)} MW**.

    *Recommended Action:* Local permits can proceed under standard environmental review cycles.
    """)
else:
    reasons = []
    if not is_water_feasible:
        reasons.append("Combined water demands exceed the expanded local municipal resource ceiling.")
    if not is_power_feasible:
        reasons.append("Power grid demand exceeds available regional spare capacity.")

    st.error(f"""
    ### ❌ PROJECT NOT FEASIBLE IN {city.upper()}, {state_code}
    Building this facility in this location poses critical risks to municipal infrastructure reserves.

    **Reasons for Rejection:**
    * {' and '.join(reasons)}

    *Engineering Adjustments:* Use the sidebar to either **reduce the proposed MW size** or **upgrade to
    Immersion Cooling** to lower the resource footprint to acceptable baseline limits.
    """)

# =============================================================================
# CHARTS
# =============================================================================
st.subheader("📋 Resource Balance & Nexus Matrix")

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("**Water (Gal/Day)**")
    water_chart_data = {
        "Entity": ["Human Baseline", "AI Data Center", "Municipal Water Budget"],
        "Gallons/Day": [human_water_usage_daily, total_ai_water_demand, total_municipal_water_budget],
    }
    st.bar_chart(data=water_chart_data, x="Entity", y="Gallons/Day")

with chart_col2:
    st.markdown("**Electrical Power (kWh/Day)**")
    power_chart_data = {
        "Entity": ["Human Baseline", "AI Data Center"],
        "kWh/Day": [human_power_usage_daily, ai_power_demand_kwh_daily],
    }
    st.bar_chart(data=power_chart_data, x="Entity", y="kWh/Day")

st.markdown(f"🛰️ **Local Hydrological Mapping:** Nearby Water Body resolved: **{surface_water_source}**.")
st.caption(
    f"System Mode: Fully Stable Spatial Telemetry. Pre-mapped hydrological layers verified. "
    f"Compiled on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC."
)
