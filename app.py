import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="WDI Sustainability Dashboard",
    layout="wide"
)

# Sidebar
st.sidebar.title("WDI Dashboard")
st.sidebar.markdown("Explore exchange rate volatility and sustainable development indicators.")

# Filters 
st.sidebar.header("Filters")
# country_filter = st.sidebar.multiselect("Select Countries", options=[])
# year_filter = st.sidebar.slider("Year Range", 2000, 2023, (2000, 2023))

# Main area 
tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Trends", "Compare", "About"])

with tab1:
    st.header("Global Overview")
    st.info("Choropleth map will go here.")

with tab2:
    st.header("Trends Over Time")
    st.info("Line charts will go here.")

with tab3:
    st.header("Country Comparison")
    st.info("Bar / scatter charts will go here.")

with tab4:
    st.header("About")
    st.markdown("""
    **Data source:** World Development Indicators, World Bank (2026)  
    **Indicators used:**
    - `PA.NUS.FCRF` — Official exchange rate (LCU per US$)
    - `NY.GDP.PCAP.CD` — GDP per capita (current US$)
    - `SI.POV.DDAY` — Poverty headcount ratio at $2.15/day
    
    **Purpose:** This dashboard was created to explore the relationship between 
    currency exchange rate volatility and sustainable development outcomes 
    across fragile and developing states.
    """)