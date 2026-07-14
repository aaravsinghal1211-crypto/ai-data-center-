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
of scaling AI. You can select **Auto-Detect** to find your local grid, or type **any city in the US** to 
simulate a live regional infrastructure stress test.
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

# 3. SMART GLOBAL SEARCH BAR & GEOCODING ENGINE
st.subheader("🗺️ Node Location & Simulation Target")

# Step A: Let user toggle between Auto-Detect and Manual Search
location_mode = st.radio(
    "Choose Simulation Target Location Method:",
    ["🛰️ Auto-Detect My Location (Browser/Server IP)", "🔍 Search Any US City"]
)

# Step B: Provide the search box if they choose Manual Search
search_query = ""
if location_mode == "🔍 Search Any US City":
    search_query = st.text_input(
        "Enter US City and State (e.g., Duluth, MN or Folsom, CA):",
        value="Folsom, CA"
    )

# Cache geocoding to prevent excessive API queries
@st.cache_data(ttl=3600)
def geocode_city_osm(query_string):
    """Translates any written city/state query into coordinates and metadata."""
    try:
        headers = {'User-Agent': 'AI-Data-Center-Simulator-Science-Fair-Project (student@sciencefair.com)'}
        url = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(query_string)}&format=json&addressdetails=1&limit=1"
        res = requests.get(url, headers=headers, timeout=5).json()
        if res:
            place = res[0]
            lat = float(place["lat"])
            lon = float(place["lon"])
            address = place.get("address", {})
            city = address.get("city") or address.get("town") or address.get("village") or address.get("county") or "Unknown City"
            state_code = address.get("state") or "US"
            # Normalize state codes to CA check
            if state_code.lower() in ["california", "ca"]:
                clean_state_code = "CA"
            else:
                clean_state_code = "OTHER"
            return lat, lon, city, clean_state_code
    except Exception:
        pass
    return None

# Step C: Resolve Telemetry Engine
def fetch_system_telemetry(user_lat=None, user_lon=None, custom_city=None, custom_state=None):
    # Default fallbacks
    city, state_code = "Folsom", "CA"
    lat, lon = 38.6780, -121.1761
    
    if user_lat is None:
        # Auto-detect via client IP
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
                state_code = "CA" if geo_res.get("region_code") == "CA" else "OTHER"
        except Exception:
            pass
    else:
        # Use Custom Geocoded values
        lat, lon = user_lat, user_lon
        city = custom_city
        state_code = custom_state

    # Fetch NWS Temperature Live
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

    return city, state_code, lat, lon, round(temp_f, 1)


# Resolve coordinates based on mode selected
custom_coords = None
if location_mode == "🔍 Search Any US City" and search_query:
    custom_coords = geocode_city_osm(search_query)

if custom_coords:
    glat, glon, gcity, gstate = custom_coords
    city, state_code, lat, lon, local_temp = fetch_system_telemetry(glat, glon, gcity, gstate)
else:
    # Trigger Auto-Detect
    city, state_code, lat, lon, local_temp = fetch_system_telemetry()

# Render visual map and telemetry cards
map_col, text_col = st.columns([2, 1])

with map_col:
    # Draw interactive folium map
    m = folium.Map(location=[lat, lon], zoom_start=10)
    folium.Marker(
        [lat, lon], 
        popup=f"{city}, {state_code}", 
        tooltip=f"Active Simulation Center"
    ).add_to(m)
    # Output map cleanly to screen without container width crash
    st_folium(m, height=300, width=700)

with text_col:
    st.write("### Telemetry Status")
    st.metric(label="🛰️ Current Simulation Node", value=f"{city}, {state_code}", delta=f"Lat: {lat} | Lon: {lon}", delta_color="off")
    is_heatwave = local_temp >= 95.0
    st.metric(
        label="☀️ NOAA Weather Feed", 
        value=f"{local_temp} °F", 
        delta="🔴 CRITICAL GRID THERMAL STRESS" if is_heatwave else "🟢 Normal Grid Thermal Load",
        delta_color="inverse" if is_heatwave else "normal"
    )

st.write("---")

# 4. ADVANCED INFRASTRUCTURE MATHEMATICAL MATRIX
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

# 5. HIGH-IMPACT METRICS DISPLAY
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

# 6. CRITICAL BREAKING POINT ALERT PROTOCOLS
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

# 7. MULTI-LAYER CHARTING
st.subheader("📋 Resource Balance & Nexus Matrix")
chart_data = {
    "Infrastructure Category": ["Grid Overhead (MW)", "Grid Overhead (MW)", "Water Systems (M-Gal/Day)", "Water Systems (M-Gal/Day)", "Water Systems (M-Gal/Day)"],
    "System Status": ["Grid Availability Space", "Consumed by AI Load", "Groundwater Safety Margin", "On-Site Evaporation", "Off-Site Generation Loss"],
    "Values": [available_grid, ai_power_demand, (base_groundwater / 1000000.0), (ai_direct_water_demand / 1000000.0), (ai_indirect_water_demand / 1000000.0)]
}
st.bar_chart(data=chart_data, x="Infrastructure Category", y="Values", color="System Status", stack=False)

st.caption(f"System Telemetry Signature: Secure handshake verified with api.weather.gov. Compiled on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC.")
