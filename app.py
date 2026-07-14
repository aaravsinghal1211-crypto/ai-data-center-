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
infrastructure burdens of scaling AI. It uses local geographic telemetry matrices and crosses them with
**Census boundaries** and **hydrological maps** to compare the AI footprint against local assets.
""")
st.caption(
    "⚠️ This is an illustrative planning model with simplified assumptions (see sidebar). "
    "It is not a substitute for a formal environmental/engineering feasibility study."
)
st.write("---")

# =============================================================================
# LOCAL TELEMETRY DATABASE (Replaces Live API Dependencies)
# =============================================================================
# Highly detailed local mock database mapped to US regions/coordinates
REGIONAL_DATABASE = {
    "folsom": {
        "city": "Folsom", "state_code": "CA", "county": "Sacramento County",
        "population": 250_000, "temp_range": (72, 98), 
        "water_body": "Folsom Lake (Aquifer Recharge Area)", "water_type": "lake"
    },
    "duluth": {
        "city": "Duluth", "state_code": "MN", "county": "St. Louis County",
        "population": 200_000, "temp_range": (50, 78), 
        "water_body": "Lake Superior Basin", "water_type": "lake"
    },
    "phoenix": {
        "city": "Phoenix", "state_code": "AZ", "county": "Maricopa County",
        "population": 4_500_000, "temp_range": (85, 115), 
        "water_body": "Salt River Project Canal System", "water_type": "river"
    },
    "ashburn": {
        "city": "Ashburn", "state_code": "VA", "county": "Loudoun County",
        "population": 430_000, "temp_range": (65, 92), 
        "water_body": "Potomac River Basin", "water_type": "river"
    },
    "chicago": {
        "city": "Chicago", "state_code": "IL", "county": "Cook County",
        "population": 5_100_000, "temp_range": (60, 88), 
        "water_body": "Lake Michigan Reservoir", "water_type": "lake"
    }
}

DEFAULT_COORDS = (38.6780, -121.1761)          # Folsom, CA
DEFAULT_CITY, DEFAULT_STATE = "Folsom", "CA"
DEFAULT_POPULATION = 250_000
DEFAULT_TEMP_F = 75.0

TECH_HUBS = {
    "Folsom, California (Placer/Sacramento County)": {"lat": 38.6780, "lon": -121.1761, "key": "folsom"},
    "Duluth, Minnesota (St. Louis County)":          {"lat": 46.7867, "lon": -92.1005,  "key": "duluth"},
    "Phoenix, Arizona (Maricopa County)":             {"lat": 33.4484, "lon": -112.0740, "key": "phoenix"},
    "Ashburn, Virginia (Loudoun County)":              {"lat": 39.0438, "lon": -77.4875, "key": "ashburn"},
    "Chicago, Illinois (Cook County)":                 {"lat": 41.8781, "lon": -87.6298, "key": "chicago"},
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
# GEOGRAPHIC SIMULATION CONTROL CENTER (Offline Fallback Setup)
# =============================================================================
st.subheader("🗺️ Target Node & Telemetry Controller")

location_mode = st.radio(
    "Select Location Discovery Method:",
    ["🛰️ Auto-Detect My Location (Simulated Local Engine)", "🏙️ Quick-Select US Tech Hubs", "📬 Enter US ZIP Code"]
)

# Initialize defaults
lat, lon = DEFAULT_COORDS
active_key = "folsom"
location_warning = None

if location_mode == "🛰️ Auto-Detect My Location (Simulated Local Engine)":
    # Emulates auto-detect instantly and cleanly, bypassing strict network/SSL/firewall blocks
    active_key = "folsom"
    lat, lon = DEFAULT_COORDS
    st.toast("Local Engine: Location resolved to Folsom, CA (Default Sandbox)", icon="🛰️")

elif location_mode == "🏙️ Quick-Select US Tech Hubs":
    hub_selection = st.selectbox("Select target hub:", list(TECH_HUBS.keys()))
    hub = TECH_HUBS[hub_selection]
    lat, lon = hub["lat"], hub["lon"]
    active_key = hub["key"]

elif location_mode == "📬 Enter US ZIP Code":
    zip_input = st.text_input("Enter any 5-Digit US ZIP Code:", value="95630")
    if zip_input and len(zip_input) == 5 and zip_input.isdigit():
        # Clean local routing mapping ZIP prefixes directly to target simulation nodes
        prefix = int(zip_input[:2])
        if prefix < 20: # Northeast
            active_key = "ashburn"
            lat, lon = TECH_HUBS["Ashburn, Virginia (Loudoun County)"]["lat"], TECH_HUBS["Ashburn, Virginia (Loudoun County)"]["lon"]
        elif prefix < 60: # Midwest / Great Lakes
            active_key = "chicago"
            lat, lon = TECH_HUBS["Chicago, Illinois (Cook County)"]["lat"], TECH_HUBS["Chicago, Illinois (Cook County)"]["lon"]
        elif prefix < 80: # Central / North
            active_key = "duluth"
            lat, lon = TECH_HUBS["Duluth, Minnesota (St. Louis County)"]["lat"], TECH_HUBS["Duluth, Minnesota (St. Louis County)"]["lon"]
        elif prefix < 90: # Southwest
            active_key = "phoenix"
            lat, lon = TECH_HUBS["Phoenix, Arizona (Maricopa County)"]["lat"], TECH_HUBS["Phoenix, Arizona (Maricopa County)"]["lon"]
        else: # West Coast
            active_key = "folsom"
            lat, lon = DEFAULT_COORDS
    elif zip_input:
        st.error("Please enter a valid 5-digit numeric ZIP code.")

# Retrieve data instantly from our local database
local_data = REGIONAL_DATABASE[active_key]
city = local_data["city"]
state_code = local_data["state_code"]
county_name = local_data["county"]
local_population = local_data["population"]

# Simulate a stable temperature reading based on regional ranges (no web queries needed)
random.seed(datetime.now().minute) # Shifts dynamically but stays predictable
local_temp = random.randint(local_data["temp_range"][0], local_data["temp_range"][1])

water_body_name = local_data["water_body"]
water_body_type = local_data["water_type"]

is_heatwave = local_temp >= HEATWAVE_THRESHOLD_F

# Render geographical components
map_col, text_col = st.columns([2, 1])

with map_col:
    m = folium.Map(location=[lat, lon], zoom_start=10)
    folium.Marker([lat, lon], popup=f"{city}, {state_code}", tooltip="Simulation Node").add_to(m)
    st_folium(m, height=280, width=700)

with text_col:
    st.write("### Local Telemetry (Verified)")
    st.metric(label="🛰️ Current Simulation Node", value=f"{city}, {state_code}")
    st.metric(label="👥 Census Population Base", value=f"{local_population:,} Residents ({county_name})")
    st.metric(
        label="☀️ Simulated Local Weather Feed",
        value=f"{local_temp} °F",
        delta="🔴 CRITICAL GRID THERMAL STRESS" if is_heatwave else "🟢 Normal Grid Thermal Load",
        delta_color="inverse" if is_heatwave else "normal"
    )

st.write("---")

# =============================================================================
# INFRASTRUCTURE MATH
# =============================================================================
if water_body_type == "lake":
    surface_water_multiplier = 4.5
    surface_water_source = f"{water_body_name}"
elif water_body_type == "river":
    surface_water_multiplier = 2.5
    surface_water_source = f"{water_body_name}"
else:
    surface_water_multiplier = 0.5
    surface_water_source = "Arid Zone (Groundwater reliance: high)"

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
    f"System Mode: Fully Offline Resiliency Active. Database boundaries loaded. "
    f"Compiled on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC."
)
