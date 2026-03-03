import streamlit as st
import requests
import time
import pandas as pd

st.title("Predictability-API // Stability Hub")

# Create live-updating placeholders
metric_col1, metric_col2 = st.columns(2)
chart_place = st.empty()

ping_buffer = []

while True:
    try:
        # Pings your updated api.py
        data = requests.get("http://localhost:10000/api/v1/network/stability").json()
        
        metric_col1.metric("Latency", f"{data['latency_ms']} ms")
        metric_col2.metric("P-Score", f"{data['p_score']}%")
        
        ping_buffer.append(data['latency_ms'])
        if len(ping_buffer) > 50: ping_buffer.pop(0)
        
        chart_place.line_chart(ping_buffer)
    except:
        st.warning("Waiting for API connection...")
        
    time.sleep(1)