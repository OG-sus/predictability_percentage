import json
import numpy as np

try:
    with open('battle_results.json', 'r') as f:
        data = json.load(f)

    # Grab latencies from the 10 runs
    latencies = [res['latencyMs'] for res in data['results']]
    
    avg_lat = np.mean(latencies)
    jitter = np.std(latencies)
    stability_score = max(0, 100 - (jitter / avg_lat * 100))

    print(f"\n" + "="*40)
    print(f" 💎 DEEPSEEK STABILITY AUDIT 💎")
    print(f"="*40)
    print(f" Samples:    {len(latencies)}")
    print(f" Avg Latency: {avg_lat/1000:.2f}s")
    print(f" Jitter:      {jitter/1000:.2f}s")
    print(f" STABILITY:   {stability_score:.1f}%")
    print(f"="*40)

except Exception as e:
    print(f"Error: Ensure you ran the 10-repeat eval first. {e}")