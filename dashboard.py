import streamlit as st
import requests
import time
import pandas as pd

st.title("Predictability-API // Stability Hub")

# 1. Create permanent 'Placeholders' so the page doesn't grow/scroll
metric_row = st.columns(2)
latency_display = metric_row[0].empty()
pscore_display = metric_row[1].empty()
chart_display = st.empty()

# 2. The Logic Loop
while True:
    try:
        # Pull from your locally running api.py
        response = requests.get("http://localhost:10000/api/v1/network/stability").json()
        
        # 3. OVERWRITE the placeholders (This stops the scrolling)
        latency_display.metric("Latency", f"{response['latency_ms']} ms")
        pscore_display.metric("P-Score", f"{response['p_score']}%")
        
        # Update your rolling chart here
        # chart_display.line_chart(your_data_list)
        
    except Exception as e:
        st.error(f"Sync Lost: {e}")
    
    time.sleep(1)