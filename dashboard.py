import streamlit as st
import requests
import time
import pandas as pd

st.title("Predictability-API // Stability Hub")

# --- THE HUD LAYOUT ---
# 1. Permanent Memory
if 'ping_history' not in st.session_state:
    st.session_state.ping_history = []

# 2. Static Containers
col1, col2 = st.columns(2)
lat_box = col1.empty()
pscore_box = col2.empty()
chart_box = st.empty() # THIS IS WHERE THE GRAPH LIVES

while True:
    try:
        r = requests.get("http://localhost:10000/api/v1/network/stability").json()
        
        # 3. Update the history
        st.session_state.ping_history.append(r['latency_ms'])
        
        # Keep the window to 60 seconds (1 minute of history)
        if len(st.session_state.ping_history) > 60:
            st.session_state.ping_history.pop(0)
            
        # 4. Overwrite the UI (No Scrolling)
        lat_box.metric("LATENCY", f"{r['latency_ms']} ms")
        pscore_box.metric("P-SCORE", f"{r['p_score']}%")
        
        # 5. RENDER THE GRAPH
        # We pass the whole list so it draws the line
        chart_box.line_chart(st.session_state.ping_history)
        
    except Exception as e:
        st.warning("Awaiting Engine Heartbeat...")
    time.sleep(1)