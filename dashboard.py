import streamlit as st
import requests
import time
import pandas as pd

# 1. Page Setup
st.set_page_config(page_title="FSR Stability Hub", layout="wide")

# Institutional HUD Styling
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {padding-top: 1rem;}
    .status-box {
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 24px;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("Predictability-API // Stability Hub")

# 2. Memory (Last 60 seconds)
if 'history' not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=['Latency', 'P-Score'])

# 3. Fixed UI Placeholders
status_placeholder = st.empty()
m1, m2 = st.columns(2)
lat_box = m1.empty()
pscore_box = m2.empty()
chart_box = st.empty()

# 4. The Loop
while True:
    try:
        # Get the Truth from api.py
        r = requests.get("http://localhost:10000/api/v1/network/stability", timeout=1).json()
        score = r['p_score']
        
        # DETERMINE COLOR & STATUS
        if score > 85:
            color = "#00ff00" # Institutional Green
            label = "INSTITUTIONAL STABILITY"
        elif score > 50:
            color = "#ffff00" # Warning Yellow
            label = "NETWORK JITTER DETECTED"
        else:
            color = "#ff0000" # Danger Red
            label = "VOLATILITY ALERT: CRITICAL"

        # Update Status Bar
        status_placeholder.markdown(
            f'<div class="status-box" style="background-color: {color}44; border: 2px solid {color}; color: {color};">'
            f'{label}</div>', 
            unsafe_allow_html=True
        )

        # Update Metrics
        lat_box.metric("LATENCY", f"{r['latency_ms']} ms")
        pscore_box.metric("P-SCORE", f"{score}%")
        
        # Update Sliding Window
        new_entry = pd.DataFrame({'Latency': [r['latency_ms']], 'P-Score': [score]})
        st.session_state.history = pd.concat([st.session_state.history, new_entry], ignore_index=True)
        if len(st.session_state.history) > 60:
            st.session_state.history = st.session_state.history.iloc[1:].reset_index(drop=True)
            
        # Draw Graph
        chart_box.line_chart(st.session_state.history)
        
    except Exception as e:
        status_placeholder.error("Connecting to Predictability Engine...")
    
    time.sleep(1)