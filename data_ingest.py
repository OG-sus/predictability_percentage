import time
import subprocess
import re
from collections import deque
import numpy as np

class GlobalState:
    latency_history = deque(maxlen=100)
    last_ping = 0.0
    p_score = 1.0  # Default to perfect stability

state = GlobalState()

def run_ingestor():
    while True:
        try:
            # High-performance ping extraction
            output = subprocess.check_output(["ping", "-n", "1", "8.8.8.8"]).decode()
            match = re.search(r"time[=<]\s*([\d.]+)\s*ms", output)
            
            if match:
                current_ms = float(match.group(1))
                state.latency_history.append(current_ms)
                state.last_ping = current_ms
                
                # Logic from fsr.py: Calculate P-score via CV
                if len(state.latency_history) > 5:
                    cv = np.std(state.latency_history) / np.mean(state.latency_history)
                    # Simple stability metric: 1 - CV (capped at 0-1)
                    state.p_score = max(0, min(1, 1 - cv))
            
            time.sleep(1) # Frequency of your ticker
        except Exception as e:
            print(f"Ingest Error: {e}")