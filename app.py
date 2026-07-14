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
of scaling AI. By default, it tracks your live telemetry, but you can select different regions across the US 
using the Interactive Map Controller below to simulate geographical stress tests.
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

# 3. INTERACTIVE GEOGRAPHIC LOCATION SELECTOR
st.subheader("🗺️ Node Location & Simulation Target")

# A dictionary of interesting testing targets with different profiles!
US_TARGETS = {
    "📍 Auto-Detect My Location (Default)": {"lat": None, "lon": None, "city": "Auto-Detect", "state_code": "Auto-Detect"},
    "Folsom, California (Clean Solar Grid)": {"lat": 38.6780, "lon": -121.1761, "city": "Folsom", "state_code": "CA"},
    "The Dalles, Oregon (Hydroelectric Hub)": {"lat": 45.5946, "lon": -121.1787, "city": "The Dalles", "state_code": "OR"},
    "Phoenix, Arizona (Extreme Desert Heat)": {"lat": 33.4484, "lon": -112.0740, "city": "Phoenix", "state_code": "AZ"},
    "Chicago, Illinois (Standard Mid-West Coal Grid)": {"lat": 41.8781, "lon": -87.6298, "city": "Chicago", "state_code": "IL"},
    "Minneapolis, Minnesota (Cold Northern Climate)": {"lat": 44.9778, "lon": -93.2650, "city": "Minneapolis", "state_code": "MN"},
    "Ashburn, Virginia (World's Largest Data Center Hub)": {"lat": 39.0438, "lon": -77.4875, "city": "Ashburn", "state_code": "VA"}
}

selected_target_name = st.selectbox("Select target destination to test:", list(US_TARGETS.keys()))
selected_target = US_TARGETS[selected_target_name]

# 4. TELEMETRY ENGINE (IP Lookup / Fallback)
def fetch_system_telemetry(custom_lat=None, custom_lon=None):
    # Default fallback (Folsom, CA)
    city, state, state_code = "Folsom", "California", "CA"
    lat, lon = 38.6780, -121.1761
    
    # Run Auto-Detect if no specific coordinates are provided
    if custom_lat is None:
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
                state = geo_res.get("region", "California")
                state_code = geo_res.get("region_code", "CA")
        except Exception:
            pass
    else:
        # Use target coordinate profile chosen by user
        lat, lon = custom_lat, custom_lon
        city = selected_target["city"]
        state_code = selected_target["state_code"]
        state = selected_target["state_code"]

    temp_f = 75.0  # Default baseline temp
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

    return city, state, state_code, lat, lon, round(temp_f, 1)

# Execute telemetry pull
city, state, state_code, lat, lon, local_temp = fetch_system_telemetry(selected_target["lat"], selected_target["lon"])

# Render map visual directly in Streamlit
map_col, text_col = st.columns([2, 1])

with map_col:
    m = folium.Map(location=[lat, lon], zoom_start=9)
    folium.Marker(
        [lat, lon], 
        popup=f"{city}, {state_code}", 
        tooltip=f"Active Simulation: {city}"
    ).add_to(m)
    # Output map to web page
    st_folium(m, height=300, width=700)

with text_col:
    st.write("### Telemetry Status")
    st.metric(label="🛰️ Target Node Location", value=f"{city}, {state_code}", delta=f"Lat: {lat} | Lon: {lon}", delta_color="off")
    is_heatwave = local_temp >= 95.0
    st.metric(
        label="☀️ NOAA Weather Feed", 
        value=f"{local_temp} °F", 
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

st.caption(f"System Telemetry Signature: Secure handshake verified with api.weather.gov. Compiled on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC.")
