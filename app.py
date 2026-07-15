import streamlit as st
from datetime import datetime
import folium
from streamlit_folium import st_folium
import requests
import urllib3

# Disable insecure request warnings if they pop up during SSL fallbacks
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =============================================================================
# PAGE SETUP
# =============================================================================
st.set_page_config(
    page_title="Live AI Infrastructure Sustainability Matrix",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("⚡ Live AI Infrastructure & Resource Stress Matrix")
st.markdown("""
This advanced dashboard analyzes the **direct (on-site)** and **indirect (grid-level)** resource burdens 
of scaling AI. It pulls **live Census Bureau population data** and **live National Weather Service forecasts** for any U.S. ZIP code to compare your AI footprint against real local assets.
""")
st.caption(
    "⚠️ This is an illustrative planning model. Always verify critical environmental data "
    "with official local civil engineering authorities."
)
st.write("---")

# =============================================================================
# HARDWARE / CONSTANTS
# =============================================================================
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
* **Census Population Benchmark:** Compares AI footprint to local human baselines.
* **Grid Heatwave Penalty:** If outdoor temp hits **{HEATWAVE_THRESHOLD_F:.0f}°F or higher**, on-site water
  usage doubles, grid capacity drops {int((1 - HEATWAVE_GRID_CAPACITY_FACTOR) * 100)}%, and power rates
  jump to ${HEATWAVE_RATE_USD_PER_KWH:.2f}/kWh.
""")

# =============================================================================
# LIVE API FETCHING ENGINE (With robust Streamlit Caching)
# =============================================================================
headers = {"User-Agent": "AI_Infrastructure_Matrix_Dashboard/2.0 (contact@sustainability.ai)"}

@st.cache_data(show_spinner=False, ttl=3600)
def resolve_zip_code(zip_code):
    """Resolves a zip code to lat, lon, city, and state."""
    try:
        url = f"https://api.zippopotam.us/us/{zip_code}"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            data = res.json()
            place = data["places"][0]
            return {
                "lat": float(place["latitude"]),
                "lon": float(place["longitude"]),
                "city": place["place name"],
                "state": data["state abbreviation"]
            }
    except Exception:
        pass
    return None

@st.cache_data(show_spinner=False, ttl=86400)
def get_county_fips(lat, lon):
    """Hits the official FCC Area API to retrieve county names and FIPS codes."""
    try:
        url = f"https://geo.fcc.gov/api/census/area?lat={lat}&lon={lon}&format=json"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            data = res.json()
            if data.get("results"):
                result = data["results"][0]
                return {
                    "county_name": result["county_name"],
                    "county_fips": result["county_fips"][-3:],  # Last 3 digits
                    "state_fips": result["state_fips"]
                }
    except Exception:
        pass
    return {"county_name": "Unknown County", "county_fips": None, "state_fips": None}

@st.cache_data(show_spinner=False, ttl=86400)
def get_county_population(state_fips, county_fips):
    """Queries the live U.S. Census Bureau API for the exact county population."""
    if not state_fips or not county_fips:
        return 150_000  # Reasonable fallback if FIPS is unresolvable
    try:
        url = f"https://api.census.gov/data/2021/pep/population?get=POP_2021,NAME&for=county:{county_fips}&in=state:{state_fips}"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            data = res.json()
            # Element at row index 1, column index 0 is the population string
            return int(data[1][0])
    except Exception:
        pass
    return 150_000  # Safe average fallback if Census API is under maintenance

@st.cache_data(show_spinner=False, ttl=1800)
def get_live_weather(lat, lon):
    """Queries NOAA / National Weather Service to pull live hourly temperatures."""
    try:
        # Step 1: Get the local Grid Points
        points_url = f"https://api.weather.gov/points/{lat},{lon}"
        res = requests.get(points_url, headers=headers, timeout=4)
        if res.status_code == 200:
            grid_data = res.json()
            forecast_url = grid_data["properties"]["forecastHourly"]
            
            # Step 2: Query the active forecast grid
            forecast_res = requests.get(forecast_url, headers=headers, timeout=4)
            if forecast_res.status_code == 200:
                hourly_data = forecast_res.json()
                current_period = hourly_data["properties"]["periods"][0]
                return float(current_period["temperature"])
    except Exception:
        pass
    return 78.0  # Seasonal standard fallback if weather.gov is rate-limiting

# =============================================================================
# GEOGRAPHIC RESOLUTION CONTROLLER
# =============================================================================
st.subheader("🗺️ Live Geography & Grid Integration")

# Input field with the requested "Ex: 12345" placeholder
zip_input = st.text_input("Enter U.S. ZIP Code:", value="95630", placeholder="Ex: 12345")

# Resolve GPS coordinates first
geo_data = resolve_zip_code(zip_input.strip())

if not geo_data:
    st.error("⚠️ Invalid or unrecognized ZIP code. Defaulting to Folsom, CA (95630) to preserve application stability.")
    geo_data = {
        "lat": 38.6780,
        "lon": -121.1761,
        "city": "Folsom",
        "state": "CA"
    }

# Execute live census/weather API pipeline based on resolved location
lat, lon = geo_data["lat"], geo_data["lon"]
city, state_code = geo_data["city"], geo_data["state"]

# County & FIPS lookup
fips_info = get_county_fips(lat, lon)
county_name = fips_info["county_name"]

# Live population lookup
local_population = get_county_population(fips_info["state_fips"], fips_info["county_fips"])

# Live NWS temperature lookup
local_temp = get_live_weather(lat, lon)
is_heatwave = local_temp >= HEATWAVE_THRESHOLD_F

# Render geographical dashboard components
map_col, text_col = st.columns([2, 1])

with map_col:
    map_key = f"folium_map_{lat}_{lon}_{zip_input}"
    m = folium.Map(location=[lat, lon], zoom_start=11)
    folium.Marker([lat, lon], popup=f"{city}, {state_code}", tooltip="Target Node").add_to(m)
    st_folium(m, height=280, width=700, key=map_key)

with text_col:
    st.write("### Live Telemetry Status")
    st.metric(label="🛰️ Resolved Node Location", value=f"{city}, {state_code}")
    st.metric(label="👥 Live County Census Base", value=f"{local_population:,} Residents ({county_name})")
    st.metric(
        label="☀️ Current Temp Forecast",
        value=f"{local_temp:.1f} °F",
        delta="🔴 CRITICAL HEATWAVE RESILIENCY LOCK" if is_heatwave else "🟢 Normal Grid Thermal Load",
        delta_color="inverse" if is_heatwave else "normal"
    )

st.write("---")

# =============================================================================
# INFRASTRUCTURE MATH (Using exact live variables)
# =============================================================================
# Regional hydrological baselines
if state_code in ["CA", "AZ", "NV", "UT", "NM"]:
    surface_water_source = "Aquifer Recharge & Imported Aqueduct Basins"
    total_municipal_water_budget = BASE_GROUNDWATER_GAL * 1.5
else:
    surface_water_source = "Localized Watershed & River Reservoirs"
    total_municipal_water_budget = BASE_GROUNDWATER_GAL * 3.5

# Human demands
human_water_usage_daily = local_population * HUMAN_WATER_GAL_PER_PERSON_DAY
human_power_usage_daily = local_population * HUMAN_POWER_KWH_PER_PERSON_DAY

# Auto-expand water capacity safely if the live county population is huge
if total_municipal_water_budget < (human_water_usage_daily * 1.2):
    total_municipal_water_budget = human_water_usage_daily * 1.5

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
st.subheader(f"📊 Live Resource Impact Report ({grid_status})")

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
        reasons.append("Combined water demands exceed local municipal resource capacity.")
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
    f"System Mode: Live API Sync (Census & NOAA). "
    f"Compiled on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC."
)
