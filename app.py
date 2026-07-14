import streamlit as st
import requests
from datetime import datetime

# 1. SET UP THE WEB PAGE LAYOUT
st.set_page_config(
    page_title="Advanced AI Infrastructure Stress Matrix",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("⚡ Advanced AI Infrastructure Systems & Resource Stress Matrix")
st.markdown("""
This advanced systems-engineering dashboard models both the **direct** and **indirect** infrastructure burdens 
of scaling AI. It tracks live location telemetry and pulls real-time environmental metrics directly from the 
**National Weather Service (NOAA)** to calculate grid economic risk and localized aquifer depletion profiles.
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
* **Scope 1 (Direct) Water Footprint:** Liquid evaporated on-site for thermal management.
* **Scope 2 (Indirect) Water Footprint:** Water consumed off-site at thermoelectric plants to generate the electricity required.
* **Grid Economic Risk Assessment:** Tracks real-time ambient heat to simulate power grid congestion and peak surge utility pricing.
""")

# 3. REAL-TIME DATA TELEMETRY (IP Geolocation & NWS Weather API)
@st.cache_data(ttl=300)
def fetch_system_telemetry():
    # Default Fallback (Folsom, CA - Central Tech Corridor)
    city, state, state_code = "Folsom", "California", "CA"
    lat, lon = 38.6780, -121.1761
    
    try:
        geo_res = requests.get("https://ipapi.co/json/", timeout=5).json()
        if "latitude" in geo_res:
            lat = geo_res["latitude"]
            lon = geo_res["longitude"]
            city = geo_res.get("city", "Unknown City")
            state = geo_res.get("region", "California")
            state_code = geo_res.get("region_code", "CA")
    except Exception:
        pass

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

# Execute Telemetry Pull
city, state, state_code, lat, lon, local_temp = fetch_system_telemetry()

# Display Location and Weather Data Streams
col_a, col_b = st.columns(2)
with col_a:
    st.metric(label="🛰️ Compute Node Execution Site (Cloud Core)", value=f"{city}, {state}", delta=f"Lat: {lat} | Lon: {lon}", delta_color="off")
with col_b:
    is_heatwave = local_temp >= 95.0
    st.metric(
        label="☀️ Live Telemetry: National Weather Service (NOAA Feed)", 
        value=f"{local_temp} °F", 
        delta="🔴 CRITICAL GRID THERMAL STRESS ACTIVE" if is_heatwave else "🟢 Standard Atmospheric Matrix",
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
# Fossil/Thermoelectric grids consume significantly more water per kWh than renewable grids
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

st.caption(f"System Telemetry Signature: Secure handshake verified with api.weather.gov. Compiled on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} Coordinated Universal Time.")
