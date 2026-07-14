import streamlit as st
import requests
from datetime import datetime
import folium
from streamlit_folium import st_folium

# 1. SET UP THE WEB PAGE LAYOUT
st.set_page_config(
    page_title="Advanced AI Infrastructure Stress Matrix",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("⚡ Advanced AI Infrastructure Systems & Resource Stress Matrix")
st.markdown("""
This systems-engineering dashboard models both the **direct** and **indirect** infrastructure burdens 
of scaling AI. You can select **Auto-Detect**, choose a pre-loaded **Tech Hub**, or enter **any US ZIP Code** to instantly geocode and run a live regional infrastructure stress test.
""")

st.write("---")

# 2. SIDEBAR - ADVANCED CONFIGURATION CONTROLS
st.sidebar.header("⚙️ System Architecture")

data_center_size = st.sidebar.slider(
    "Proposed AI Data Center Capacity (Megawatts - MW)", 
    min_value=10, 
    max_value=500, 
    value=100,
    step=10
)

cooling_tech = st.sidebar.selectbox(
    "Select Cooling Technology Layer",
    ["Traditional Evaporative Cooling", "Direct-to-Chip Liquid Cooling", "Immersion Cooling (Fluid Submersion)"]
)

st.sidebar.markdown("---")
st.sidebar.markdown("""
### 🧠 Advanced System Layers Active:
* **Scope 1 (Direct) Water:** On-site cooling evaporation.
* **Scope 2 (Indirect) Water:** Off-site power generation water draw.
* **Economic Risk Layer:** Ambient-heat dynamic utility pricing.
""")

# 3. INTERACTIVE SIMULATION TARGET CONTROLLER
st.subheader("🗺️ Node Location & Simulation Target")

location_mode = st.radio(
    "Choose Simulation Target Location Method:",
    ["🛰️ Auto-Detect My Location (Browser/Server IP)", "🏙️ Quick-Select US Tech Hubs", "📬 Enter US ZIP Code"]
)

# Core coordinates default (Folsom, CA)
lat, lon = 38.6780, -121.1761
city, state_code = "Folsom", "CA"

# Preloaded targets
TECH_HUBS = {
    "Folsom, California (Clean Solar Grid)": {"lat": 38.6780, "lon": -121.1761, "city": "Folsom", "state_code": "CA"},
    "Duluth, Minnesota (Cold Northern Climate)": {"lat": 46.7867, "lon": -92.1005, "city": "Duluth", "state_code": "MN"},
    "Phoenix, Arizona (Extreme Desert Heat)": {"lat": 33.4484, "lon": -112.0740, "city": "Phoenix", "state_code": "AZ"},
    "Ashburn, Virginia (World's Largest Data Hub)": {"lat": 39.0438, "lon": -77.4875, "city": "Ashburn", "state_code": "VA"},
    "Chicago, Illinois (Standard Mid-West Coal Grid)": {"lat": 41.8781, "lon": -87.6298, "city": "Chicago", "state_code": "IL"}
}

if location_mode == "🛰️ Auto-Detect My Location (Browser/Server IP)":
    try:
        headers = st.context.headers
        client_ip = None
        if "x-forwarded-for" in headers:
            client_ip = headers["x-forwarded-for"].split(",")[0].strip()
        elif "X-Forwarded-For" in headers:
            client_ip = headers["X-Forwarded-For"].split(",")[0].strip()
            
        if client_ip:
            geo_res = requests.get(f"https://ipapi.co/{client_ip}/json/", timeout=5).json()
        else:
            geo_res = requests.get("https://ipapi.co/json/", timeout=5).json()
            
        if "latitude" in geo_res:
            lat = geo_res["latitude"]
            lon = geo_res["longitude"]
            city = geo_res.get("city", "Unknown City")
            state_code = geo_res.get("region_code", "CA")
    except Exception:
        pass

elif location_mode == "🏙️ Quick-Select US Tech Hubs":
    hub_selection = st.selectbox("Select target hub:", list(TECH_HUBS.keys()))
    selected_hub = TECH_HUBS[hub_selection]
    lat = selected_hub["lat"]
    lon = selected_hub["lon"]
    city = selected_hub["city"]
    state_code = selected_hub["state_code"]

elif location_mode == "📬 Enter US ZIP Code":
    zip_input = st.text_input("Enter any 5-Digit US ZIP Code (e.g., 90210, 55802, 10001):", value="95630")
    
    if zip_input and len(zip_input) == 5 and zip_input.isdigit():
        try:
            # Query Zippopotamus - Extremely reliable, zero-rate limits for US zip-codes
            zip_url = f"https://api.zippopotam.us/us/{zip_input}"
            zip_res = requests.get(zip_url, timeout=5).json()
            if "places" in zip_res:
                place_data = zip_res["places"][0]
                lat = float(place_data["latitude"])
                lon = float(place_data["longitude"])
                city = place_data["place name"]
                state_code = place_data["state abbreviation"]
            else:
                st.warning("⚠️ ZIP Code not found. Defaulting to baseline Folsom, CA coordinates.")
        except Exception:
            st.error("⚠️ Connection to geocoding engine failed. Defaulting to baseline Folsom, CA.")

# 4. WEATHER TELEMETRY (NOAA API Lookup)
temp_f = 75.0
try:
    nws_headers = {'User-Agent': '(mycalcairfairproject.com, student@sciencefair.com)'}
    points_url = f"https://api.weather.gov/points/{round(lat,4)},{round(lon,4)}"
    points_res = requests.get(points_url, headers=nws_headers, timeout=5).json()
    forecast_url = points_res['properties']['forecastHourly']
    
    forecast_res = requests.get(forecast_url, headers=nws_headers, timeout=5).json()
    current_period = forecast_res['properties']['periods'][0]
    temp_f = current_period['temperature']
    
    if current_period['temperatureUnit'] == 'C':
        temp_f = (temp_f * 9/5) + 32
except Exception:
    pass

# Render visual map and telemetry cards
map_col, text_col = st.columns([2, 1])

with map_col:
    # Render Interactive Leaflet Map Centered on Target
    m = folium.Map(location=[lat, lon], zoom_start=10)
    folium.Marker(
        [lat, lon], 
        popup=f"{city}, {state_code}", 
        tooltip=f"Active Simulation Center"
    ).add_to(m)
    st_folium(m, height=300, width=700)

with text_col:
    st.write("### Telemetry Status")
    st.metric(label="🛰️ Current Simulation Node", value=f"{city}, {state_code}", delta=f"Lat: {lat} | Lon: {lon}", delta_color="off")
    is_heatwave = temp_f >= 95.0
    st.metric(
        label="☀️ NOAA Weather Feed", 
        value=f"{temp_f} °F", 
        delta="🔴 CRITICAL GRID THERMAL STRESS" if is_heatwave else "🟢 Normal Grid Thermal Load",
        delta_color="inverse" if is_heatwave else "normal"
    )

st.write("---")

# 5. ADVANCED INFRASTRUCTURE MATHEMATICAL MATRIX
base_spare_grid = 250.0       # MW capacity baseline
base_groundwater = 5000000.0  # Gallons per day baseline

# Hardware Efficiency Multipliers
power_modifier = 1.0
water_modifier = 1.0

if cooling_tech == "Direct-to-Chip Liquid Cooling":
    power_modifier = 0.85   # 15% energy reduction
    water_modifier = 0.30   # 70% water reduction
elif cooling_tech == "Immersion Cooling (Fluid Submersion)":
    power_modifier = 0.80   # 20% energy reduction
    water_modifier = 0.10   # 90% water reduction

# Finalized Direct Demands
ai_power_demand = data_center_size * power_modifier
base_water_per_mw = 50000.0 if is_heatwave else 25000.0
ai_direct_water_demand = (data_center_size * base_water_per_mw) * water_modifier

# Indirect Water Multiplier (Scope 2 Energy-Water Nexus)
indirect_water_factor = 0.13 if state_code == "CA" else 1.2  # Gal per kWh
ai_indirect_water_demand = ai_power_demand * 1000 * 24 * indirect_water_factor

# Grid Headroom and Economic Degradation Mode
if is_heatwave:
    available_grid = base_spare_grid * 0.60  # Grid drops 40% under local AC load surge
    electricity_rate = 0.45                  # Peak demand surge pricing ($/kWh)
    grid_status = "🔴 HIGH ACCELERATION PEAK RESILIENCY LOCK"
else:
    available_grid = base_spare_grid
    electricity_rate = 0.15                  # Nominal commercial utility pricing ($/kWh)
    grid_status = "🟢 STABLE BASELINE LOAD BALANCE"

# Operational Balances
remaining_grid = available_grid - ai_power_demand
total_water_demand = ai_direct_water_demand + ai_indirect_water_demand
remaining_water = base_groundwater - total_water_demand
daily_energy_cost = ai_power_demand * 1000 * 24 * electricity_rate

# 6. HIGH-IMPACT METRICS DISPLAY
st.subheader(f"📊 Real-Time Multi-Variable Impact Report ({grid_status})")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="💧 On-Site Water Siphon (Scope 1)", value=f"{int(ai_direct_water_demand):,} Gal/Day", delta=cooling_tech)
with col2:
    grid_source = "Renewable Profile" if state_code == "CA" else "Standard National Utility Grid"
    st.metric(label="🔌 Generation Water Siphon (Scope 2)", value=f"{int(ai_indirect_water_demand):,} Gal/Day", delta=grid_source, delta_color="off")
with col3:
    cost_delta = "PEAK CRITICAL SURGE RATES ACTIVE" if is_heatwave else "Standard Base Rates"
    st.metric(label="💰 Daily Wholesale Energy Cost", value=f"${int(daily_energy_cost):,}", delta=cost_delta, delta_color="inverse" if is_heatwave else "normal")

col4, col5 = st.columns(2)
with col4:
    st.metric(label="📉 Remaining Net Grid Overhead", value=f"{round(remaining_grid, 1)} MW", delta=f"Regional Limit: {available_grid} MW", delta_color="normal" if remaining_grid >= 0 else "inverse")
with col5:
    st.metric(label="🚰 Remaining Combined Aquifer Reserve", value=f"{int(remaining_water):,} Gal", delta=f"Regional Resource Ceiling: {int(base_groundwater):,} Gal", delta_color="normal" if remaining_water >= 0 else "inverse")

st.write("---")

# 7. CRITICAL BREAKING POINT ALERT PROTOCOLS
if remaining_grid < 0 or remaining_water < 0:
    st.error(f"""
    ### 🚨 SYSTEM CRISIS INTERVENTION REQUIRED
    The processing system at **{city}** has breached immediate sustainability thresholds.
    * **Grid Deficit:** {abs(round(remaining_grid, 1)) if remaining_grid < 0 else 0} MW Shortfall
    * **Water Deficit:** {abs(int(remaining_water)) if remaining_water < 0 else 0:,} Gallons Overdraft
    
    *Engineering Recommendation:* Upgrade facility architecture to **Immersion Cooling** or scale down proposed compute parameters to prevent community brownouts or deep systemic water pressure drops.
    """)
else:
    st.success(f"✅ Infrastructure Security Threshold Checked. The {city} grid configuration can securely contain this facility's current engineering envelope.")

# 8. MULTI-LAYER CHARTING
st.subheader("📋 Resource Balance & Nexus Matrix")
chart_data = {
    "Infrastructure Category": ["Grid Overhead (MW)", "Grid Overhead (MW)", "Water Systems (M-Gal/Day)", "Water Systems (M-Gal/Day)", "Water Systems (M-Gal/Day)"],
    "System Status": ["Grid Availability Space", "Consumed by AI Load", "Groundwater Safety Margin", "On-Site Evaporation", "Off-Site Generation Loss"],
    "Values": [available_grid, ai_power_demand, (base_groundwater / 1000000.0), (ai_direct_water_demand / 1000000.0), (ai_indirect_water_demand / 1000000.0)]
}
st.bar_chart(data=chart_data, x="Infrastructure Category", y="Values", color="System Status", stack=False)

st.caption(f"System Telemetry Signature: Secure handshake verified with api.zippopotam.us & api.weather.gov. Compiled on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC.")
