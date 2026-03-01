import json
import numpy as np

with open('battle_results.json', 'r') as f:
    data = json.load(f)

# Extract latencies for all 10 runs
latencies = [res['latencyMs'] for res in data['results']['results']]

avg_lat = np.mean(latencies)
std_dev = np.std(latencies)
# Stability Score: Higher is better (lower variance)
stability_score = max(0, 100 - (std_dev / avg_lat * 100))

print(f"\n" + "="*40)
print(f" 💎 DEEPSEEK STABILITY AUDIT 💎")
print(f"="*40)
print(f" Total Samples:  {len(latencies)}")
print(f" Avg Heartbeat:  {avg_lat:.2f}ms")
print(f" Latency Jitter: {std_dev:.2f}ms")
print(f" STABILITY SCORE: {stability_score:.2f}%")
print(f"="*40)

if stability_score > 90:
    print(" STATUS: INSTITUTIONAL GRADE")
else:
    print(" STATUS: VOLATILE ASSET")