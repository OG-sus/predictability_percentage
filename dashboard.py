import streamlit as st
import requests
import time
import pandas as pd

# 1. Page Configuration for OBS
st.set_page_config(page_title="Stability Hub", layout="wide")

# Hide Streamlit UI elements for a clean stream look
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {padding-top: 1rem;}
    </style>
""", unsafe_content_html=True)

st.title("Predictability-API // Stability Hub")

# 2. Initialize the Sliding Window (Memory)
# We use st.session_state so the data survives page refreshes
if 'history' not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=['Latency', 'P-Score'])

# 3. Create the HUD Layout (Fixed Placeholders)
col1, col2 = st.columns(2)
lat_metric = col1.empty()
pscore_metric = col2.empty()

st.subheader("Live Euler-Decay Audit")
chart_placeholder = st.empty()

# 4. The Integration Loop
while True:
    try:
        # Fetch the Truth from your local api.py
        response = requests.get("http://localhost:10000/api/v1/network/stability", timeout=1).json()
        
        curr_lat = response['latency_ms']
        curr_pscore = response['p_score']
        
        # Update Metrics
        lat_metric.metric("LATENCY", f"{curr_lat} ms")
        pscore_metric.metric("P-SCORE", f"{curr_pscore}%")
        
        # Manage the Sliding Window (Last 60 seconds)
        new_data = pd.DataFrame({'Latency': [curr_lat], 'P-Score': [curr_pscore]})
        st.session_state.history = pd.concat([st.session_state.history, new_data], ignore_index=True)
        
        if len(st.session_state.history) > 60:
            st.session_state.history = st.session_state.history.iloc[1:].reset_index(drop=True)
            
        # Update the Sliding Graph
        # We plot both to show how P-Score reacts to Latency spikes
        chart_placeholder.line_chart(st.session_state.history)
        
    except Exception as e:
        st.warning("Connecting to Predictability Engine...")
        
    time.sleep(1)