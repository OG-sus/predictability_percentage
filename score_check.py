import json
import numpy as np

with open('output.json', 'r') as f:
    data = json.load(f)

# Extracting the latency of each run from the Promptfoo export
results = data['results']['table']['body']
latencies = [row['outputs'][0]['latencyMs'] for row in results]

# Stability Network Core Math
avg = np.mean(latencies)
std = np.std(latencies)
# Predictability = 100% minus the % of variation
score = max(0, 100 - (std / avg * 100))

print(f"\n--- STABILITY NETWORK REPORT ---")
print(f"Iterations: {len(latencies)}")
print(f"Mean Latency: {avg:.2f}ms")
print(f"Predictability Score: {score:.2f}%")