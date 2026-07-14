import streamlit as st
import requests
from datetime import datetime
import folium
from streamlit_folium import st_folium
import urllib3

# Suppress insecure request warnings from disabling SSL verification (makes console clean)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

# Initialize a debug log in session state to track network errors
if "debug_log" not in st.session_state:
    st.session_state.debug_log = []

def log_debug(msg):
    st.session_state.debug_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# =============================================================================
# CONSTANTS
# =============================================================================
DEFAULT_COORDS = (38.6780, -121.1761)          # Folsom, CA
DEFAULT_CITY, DEFAULT_STATE = "Folsom", "CA"
DEFAULT_POPULATION = 250_000
DEFAULT_TEMP_F = 75.0

TECH_HUBS = {
    "Folsom, California (Placer/Sacramento County)": {"lat": 38.6780, "lon": -121.1761, "city": "Folsom", "state_code": "CA"},
    "Duluth, Minnesota (St. Louis County)":          {"lat": 46.7867, "lon": -92.1005,  "city": "Duluth", "state_code": "MN"},
    "Phoenix, Arizona (Maricopa County)":             {"lat": 33.4484, "lon": -112.0740, "city": "Phoenix", "state_code": "AZ"},
    "Ashburn, Virginia (Loudoun County)":              {"lat": 39.0438, "lon": -77.4875, "city": "Ashburn", "state_code": "VA"},
    "Chicago, Illinois (Cook County)":                 {"lat": 41.8781, "lon": -87.6298, "city": "Chicago", "state_code": "IL"},
}

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
location_warning = None

if location_mode == "🛰️ Auto-Detect My Location (Browser/Server IP)":
    try:
        log_debug("Starting IP Auto-Detection...")
        headers = st.context.headers
        client_ip = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
        if client_ip:
            client_ip = client_ip.split(",")[0].strip()
            log_debug(f"IP extracted from context headers: {client_ip}")
        
        # Fallback to ipify with SSL verification bypassed (verify=False)
        if not client_ip or client_ip in ("127.0.0.1", "localhost", "::1"):
            try:
                log_debug("Localhost detected. Pinging ipify for public IP...")
                client_ip = requests.get("https://api64.ipify.org", timeout=3, verify=False).text.strip()
                log_debug(f"Public IP fetched from ipify: {client_ip}")
            except Exception as e:
                log_debug(f"ipify call failed: {str(e)}")
                client_ip = None

        # Query geolocation via ip-api.com (we use HTTP to bypass SSL restrictions entirely)
        geo_url = f"http://ip-api.com/json/{client_ip}" if client_ip else "http://ip-api.com/json/"
        log_debug(f"Pinging Geolocation API: {geo_url}")
        geo_res = requests.get(geo_url, timeout=5).json()

        if geo_res.get("status") == "success" and "lat" in geo_res:
            lat = geo_res["lat"]
            lon = geo_res["lon"]
            city = geo_res.get("city", "Unknown City")
            state_code = geo_res.get("region", DEFAULT_STATE)
            log_debug(f"Geolocation Success: {city}, {state_code} ({lat}, {lon})")

            if geo_res.get("countryCode") not in (None, "US"):
                location_warning = (
                    f"Detected location ({city}, {geo_res.get('country', 'unknown country')}) "
                    "is outside the US. Weather and grid-rate assumptions below are US-calibrated."
                )
        else:
            log_debug(f"ip-api returned non-success status: {geo_res.get('status')}")
            location_warning = "Could not parse geolocation from IP API. Using default: Folsom, CA."
    except Exception as e:
        log_debug(f"Location auto-detection crashed: {str(e)}")
        location_warning = "Location auto-detection failed (network/API issue). Using default: Folsom, CA."

elif location_mode == "🏙️ Quick-Select US Tech Hubs":
    hub_selection = st.selectbox("Select target hub:", list(TECH_HUBS.keys()))
    hub = TECH_HUBS[hub_selection]
    lat, lon, city, state_code = hub["lat"], hub["lon"], hub["city"], hub["state_code"]
    log_debug(f"User manually selected Tech Hub: {city}")

elif location_mode == "📬 Enter US ZIP Code":
    zip_input = st.text_input("Enter any 5-Digit US ZIP Code:", value="95630")
    if zip_input and len(zip_input) == 5 and zip_input.isdigit():
        try:
            log_debug(f"Pinging ZIP lookup for code: {zip_input}")
            zip_res = requests.get(f"https://api.zippopotam.us/us/{zip_input}", timeout=5, verify=False).json()
            if "places" in zip_res:
                place = zip_res["places"][0]
                lat, lon = float(place["latitude"]), float(place["longitude"])
                city, state_code = place["place name"], place["state abbreviation"]
                log_debug(f"ZIP Resolution Success: {city}, {state_code}")
            else:
                location_warning = "ZIP Code not found. Defaulting to baseline Folsom, CA."
        except Exception as e:
            log_debug(f"ZIP Code lookup crashed: {str(e)}")
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
    county_name = "Local County"
    local_pop = DEFAULT_POPULATION
    temp_f = DEFAULT_TEMP_F
    partial = False

    # A. Query FCC Census Area API
    try:
        fcc_url = f"https://geo.fcc.gov/api/census/area?lat={lat}&lon={lon}&format=json"
        fcc_res = requests.get(fcc_url, timeout=5, verify=False).json()
        results = fcc_res.get("results") or []
        if results:
            raw_name = results[0].get("county_name", "Local County")
            county_name = raw_name
            lookup_key = raw_name.lower().replace(" county", "").strip()
            local_pop = KNOWN_COUNTY_POPULATIONS.get(lookup_key, DEFAULT_POPULATION)
        else:
            partial = True
    except Exception as e:
        log_debug(f"FCC Census API error: {str(e)}")
        partial = True

    # B. Query National Weather Service API (Bypass SSL)
    try:
        nws_headers = {"User-Agent": NWS_USER_AGENT}
        points_res = requests.get(
            f"https://api.weather.gov/points/{round(lat, 4)},{round(lon, 4)}",
            headers=nws_headers, timeout=5, verify=False
        ).json()
        forecast_url = points_res["properties"]["forecastHourly"]
        forecast_res = requests.get(forecast_url, headers=nws_headers, timeout=5, verify=False).json()
        current = forecast_res["properties"]["periods"][0]
        temp_f = current["temperature"]
        if current["temperatureUnit"] == "C":
            temp_f = (temp_f * 9 / 5) + 32
    except Exception as e:
        log_debug(f"NWS Weather API error: {str(e)}")
        partial = True

    return county_name, local_pop, round(temp_f, 1), partial


@st.cache_data(ttl=1800)
def scan_local_hydrology(lat: float, lon: float):
    # Standard 15km Overpass query
    query = f"""
    [out:json][timeout:15];
    (
      nwr["waterway"~"river|canal"](around:15000,{lat},{lon});
      nwr["natural"="water"](around:15000,{lat},{lon});
      nwr["landuse"="reservoir"](around:15000,{lat},{lon});
    );
    out tags center;
    """
    
    endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.private.coffee/api/interpreter"
    ]

    response_data = None
    success = False

    for endpoint in endpoints:
        try:
            log_debug(f"Trying Overpass Endpoint: {endpoint}")
            response = requests.get(endpoint, params={"data": query}, timeout=10, verify=False)
            if response.status_code == 200:
                response_data = response.json()
                success = True
                log_debug(f"Overpass success from endpoint: {endpoint}")
                break
            else:
                log_debug(f"Endpoint {endpoint} returned status code: {response.status_code}")
        except Exception as e:
            log_debug(f"Failed to query endpoint {endpoint}: {str(e)}")
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
            selected_lake = max(unique_lakes, key=len)
            log_debug(f"Found lake: {selected_lake}")
            return selected_lake, "lake", False
        if unique_rivers:
            selected_river = max(unique_rivers, key=len)
            log_debug(f"Found river: {selected_river}")
            return selected_river, "river", False
        
        log_debug("No features found matching lake or river inside response payload.")
        return "No major surface water bodies detected within 15km", "none", False
    except Exception as e:
        log_debug(f"Failed parsing OSM payload: {str(e)}")
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

# =============================================================================
# SYSTEM DIAGNOSTIC PANEL (For Troubleshooting Network/Firewall Blocks)
# =============================================================================
st.write("---")
with st.expander("🛠️ System Telemetry Debug Console (Click to expand if APIs are failing)"):
    st.write("If you see errors below referring to `SSLError`, `ConnectionRefused`, or `Timeout`, your local internet network/firewall is blocking outbound Python connections.")
    for entry in st.session_state.debug_log:
        st.code(entry)
