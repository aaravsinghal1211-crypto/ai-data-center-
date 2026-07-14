import streamlit as st
import requests
from datetime import datetime
import folium
from streamlit_folium import st_folium

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
infrastructure burdens of scaling AI. It pulls live regional weather telemetry and crosses it with
**Census database boundaries** and **live OpenStreetMap hydrological scans** to compare the AI footprint
against real local assets.
""")
st.caption(
    "⚠️ This is an illustrative planning model with simplified assumptions (see sidebar). "
    "It is not a substitute for a formal environmental/engineering feasibility study."
)
st.write("---")

# =============================================================================
# CONSTANTS (all model assumptions live here so they're easy to audit/tune)
# =============================================================================
DEFAULT_COORDS = (38.6780, -121.1761)          # Folsom, CA
DEFAULT_CITY, DEFAULT_STATE = "Folsom", "CA"
DEFAULT_POPULATION = 250_000                    # single source of truth for "unknown county" fallback
DEFAULT_TEMP_F = 75.0

TECH_HUBS = {
    "Folsom, California (Placer/Sacramento County)": {"lat": 38.6780, "lon": -121.1761, "city": "Folsom", "state_code": "CA"},
    "Duluth, Minnesota (St. Louis County)":          {"lat": 46.7867, "lon": -92.1005,  "city": "Duluth", "state_code": "MN"},
    "Phoenix, Arizona (Maricopa County)":             {"lat": 33.4484, "lon": -112.0740, "city": "Phoenix", "state_code": "AZ"},
    "Ashburn, Virginia (Loudoun County)":              {"lat": 39.0438, "lon": -77.4875, "city": "Ashburn", "state_code": "VA"},
    "Chicago, Illinois (Cook County)":                 {"lat": 41.8781, "lon": -87.6298, "city": "Chicago", "state_code": "IL"},
}

# County-name -> population lookup. Keys are bare county names (no "County" suffix) in lowercase.
KNOWN_COUNTY_POPULATIONS = {
    "placer": 410_000, "sacramento": 1_580_000, "st. louis": 200_000,
    "maricopa": 4_500_000, "loudoun": 430_000, "cook": 5_100_000,
}

HEATWAVE_THRESHOLD_F = 95.0
BASE_SPARE_GRID_MW = 250.0
BASE_GROUNDWATER_GAL = 5_000_000.0
HUMAN_WATER_GAL_PER_PERSON_DAY = 80.0
HUMAN_POWER_KWH_PER_PERSON_DAY = 12.0

COOLING_TECH_MODIFIERS = {
    "Traditional Evaporative Cooling":              {"power": 1.00, "water": 1.00},
    "Direct-to-Chip Liquid Cooling":                {"power": 0.85, "water": 0.30},  # -15% power, -70% water
    "Immersion Cooling (Fluid Submersion)":         {"power": 0.80, "water": 0.10},  # -20% power, -90% water
}

WATER_PER_MW_NORMAL = 25_000.0
WATER_PER_MW_HEATWAVE = 50_000.0
INDIRECT_WATER_FACTOR_CA = 0.13   # gal per kWh, CA grid mix
INDIRECT_WATER_FACTOR_OTHER = 1.2  # gal per kWh, thermoelectric-heavy grid mix

HEATWAVE_GRID_CAPACITY_FACTOR = 0.60   # -40% capacity under heatwave AC surge
HEATWAVE_RATE_USD_PER_KWH = 0.45
NORMAL_RATE_USD_PER_KWH = 0.15

# NOTE: NWS's API requires a real identifying contact per their usage policy
# (https://www.weather.gov/documentation/services-web-api). Replace before production use.
NWS_USER_AGENT = "(ai-infra-dashboard, contact: replace-with-your-email@example.com)"

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
    ["🛰️ Auto-Detect My Location (Browser/Server IP)", "🏙️ Quick-Select US Tech Hubs", "📬 Enter US ZIP Code"]
)

lat, lon = DEFAULT_COORDS
city, state_code = DEFAULT_CITY, DEFAULT_STATE
location_warning = None  # surfaced to user

if location_mode == "🛰️ Auto-Detect My Location (Browser/Server IP)":
    try:
        # Step 1: Attempt headers extraction (useful when deployed)
        headers = st.context.headers
        client_ip = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
        if client_ip:
            client_ip = client_ip.split(",")[0].strip()
        
        # Step 2: Fallback to a global IP resolution echo API if headers are blank/localhost
        if not client_ip or client_ip in ("127.0.0.1", "localhost", "::1"):
            try:
                client_ip = requests.get("https://api64.ipify.org", timeout=3).text.strip()
            except Exception:
                client_ip = None

        # Step 3: Query IP location via ip-api.com (reliable, unauthenticated)
        geo_url = f"http://ip-api.com/json/{client_ip}" if client_ip else "http://ip-api.com/json/"
        geo_res = requests.get(geo_url, timeout=5).json()

        if geo_res.get("status") == "success" and "lat" in geo_res:
            lat = geo_res["lat"]
            lon = geo_res["lon"]
            city = geo_res.get("city", "Unknown City")
            state_code = geo_res.get("region", DEFAULT_STATE)

            # NWS only covers the US
            if geo_res.get("countryCode") not in (None, "US"):
                location_warning = (
                    f"Detected location ({city}, {geo_res.get('country', 'unknown country')}) "
                    "is outside the US. Weather and grid-rate assumptions below are US-calibrated "
                    "and may not be meaningful here."
                )
        else:
            location_warning = "Could not parse geolocation from IP API. Using default: Folsom, CA."
    except Exception as e:
        location_warning = f"Location auto-detection failed ({str(e)}). Using default: Folsom, CA."

elif location_mode == "🏙️ Quick-Select US Tech Hubs":
    hub_selection = st.selectbox("Select target hub:", list(TECH_HUBS.keys()))
    hub = TECH_HUBS[hub_selection]
    lat, lon, city, state_code = hub["lat"], hub["lon"], hub["city"], hub["state_code"]

elif location_mode == "📬 Enter US ZIP Code":
    zip_input = st.text_input("Enter any 5-Digit US ZIP Code:", value="95630")
    if zip_input and len(zip_input) == 5 and zip_input.isdigit():
        try:
            zip_res = requests.get(f"https://api.zippopotam.us/us/{zip_input}", timeout=5).json()
            if "places" in zip_res:
                place = zip_res["places"][0]
                lat, lon = float(place["latitude"]), float(place["longitude"])
                city, state_code = place["place name"], place["state abbreviation"]
            else:
                location_warning = "ZIP Code not found. Defaulting to baseline Folsom, CA."
        except Exception:
            location_warning = "ZIP lookup failed (network/API issue). Defaulting to baseline Folsom, CA."
    elif zip_input:
        location_warning = "Enter a valid 5-digit US ZIP code."

if location_warning:
    st.warning(f"⚠️ {location_warning}")

# =============================================================================
# LIVE TELEMETRY (Census boundaries + NWS weather)
# =============================================================================
@st.cache_data(ttl=1800)
def fetch_location_data_streams(lat: float, lon: float):
    """Returns (county_name, population, temp_f, data_is_partial)."""
    county_name = "Local County"
    local_pop = DEFAULT_POPULATION
    temp_f = DEFAULT_TEMP_F
    partial = False

    # A. Query FCC Census Area API
    try:
        fcc_url = f"https://geo.fcc.gov/api/census/area?lat={lat}&lon={lon}&format=json"
        fcc_res = requests.get(fcc_url, timeout=5).json()
        results = fcc_res.get("results") or []
        if results:
            raw_name = results[0].get("county_name", "Local County")
            county_name = raw_name
            lookup_key = raw_name.lower().replace(" county", "").strip()
            local_pop = KNOWN_COUNTY_POPULATIONS.get(lookup_key, DEFAULT_POPULATION)
        else:
            partial = True
    except Exception:
        partial = True

    # B. Query National Weather Service API (US coverage only)
    try:
        nws_headers = {"User-Agent": NWS_USER_AGENT}
        points_res = requests.get(
            f"https://api.weather.gov/points/{round(lat, 4)},{round(lon, 4)}",
            headers=nws_headers, timeout=5
        ).json()
        forecast_url = points_res["properties"]["forecastHourly"]
        forecast_res = requests.get(forecast_url, headers=nws_headers, timeout=5).json()
        current = forecast_res["properties"]["periods"][0]
        temp_f = current["temperature"]
        if current["temperatureUnit"] == "C":
            temp_f = (temp_f * 9 / 5) + 32
    except Exception:
        partial = True

    return county_name, local_pop, round(temp_f, 1), partial


@st.cache_data(ttl=1800)
def scan_local_hydrology(lat: float, lon: float):
    """Returns (water_body_name, water_body_type, lookup_failed)."""
    # Reduced radius slightly to 15,000m (15km) to accelerate response and decrease timeout risk
    query = f"""
    [out:json][timeout:15];
    (
      nwr["waterway"~"river|canal"](around:15000,{lat},{lon});
      nwr["natural"="water"](around:15000,{lat},{lon});
      nwr["landuse"="reservoir"](around:15000,{lat},{lon});
    );
    out tags center;
    """
    
    # List of redundant Overpass API public endpoints to loop through in case of rate-limiting
    endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.private.coffee/api/interpreter"
    ]

    response_data = None
    success = False

    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, params={"data": query}, timeout=8)
            if response.status_code == 200:
                response_data = response.json()
                success = True
                break
        except Exception:
            continue

    if not success or not response_data:
        return "Hydrology scan unavailable", "none", True

    try:
        rivers, lakes = [], []
        for element in response_data.get("elements", []):
            tags = element.get("tags", {})
            name = tags.get("name") or tags.get("official_name")
            if not name:
                continue
            water_type = tags.get("water") or tags.get("natural") or tags.get("landuse")
            if water_type in ("reservoir", "lake", "basin") or "lake" in name.lower() or "reservoir" in name.lower():
                lakes.append(name)
            elif "waterway" in tags or "river" in name.lower():
                rivers.append(name)

        unique_lakes, unique_rivers = list(set(lakes)), list(set(rivers))
        if unique_lakes:
            return max(unique_lakes, key=len), "lake", False
        if unique_rivers:
            return max(unique_rivers, key=len), "river", False
        return "No major surface water bodies detected within 15km", "none", False
    except Exception:
        return "Hydrology scan evaluation failed", "none", True


with st.spinner("Pulling census, weather, and hydrology telemetry..."):
    county_name, local_population, local_temp, telemetry_partial = fetch_location_data_streams(lat, lon)
    water_body_name, water_body_type, hydrology_failed = scan_local_hydrology(lat, lon)

if telemetry_partial:
    st.info("ℹ️ Some census/weather telemetry could not be retrieved live — partial defaults were used for those fields.")
if hydrology_failed:
    st.info("ℹ️ Hydrology scan (OpenStreetMap/Overpass) is temporarily unavailable — defaulting to conservative arid-zone assumptions.")

is_heatwave = local_temp >= HEATWAVE_THRESHOLD_F

# Render geographic interface split
map_col, text_col = st.columns([2, 1])

with map_col:
    m = folium.Map(location=[lat, lon], zoom_start=10)
    folium.Marker([lat, lon], popup=f"{city}, {state_code}", tooltip="Simulation Node").add_to(m)
    st_folium(m, height=280, width=700)

with text_col:
    st.write("### Telemetry Status")
    st.metric(label="🛰️ Current Simulation Node", value=f"{city}, {state_code}")
    st.metric(label="👥 Census Population Base", value=f"{local_population:,} Residents")
    st.metric(
        label="☀️ NOAA Weather Feed",
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
    surface_water_source = f"{water_body_name} (Aquifer Recharge Area)"
elif water_body_type == "river":
    surface_water_multiplier = 2.5
    surface_water_source = f"{water_body_name} Basin"
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

st.markdown(f"🛰️ **Live Hydrological Telemetry:** Nearby Water Body detected: **{surface_water_source}**.")
st.caption(
    f"System Telemetry Signature: handshakes attempted with ipify.org, ip-api.com, geo.fcc.gov, "
    f"api.weather.gov, and overpass-api.de mirrors. "
    f"Compiled on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC."
)
