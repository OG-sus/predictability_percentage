import json
import numpy as np

def find_latencies(obj):
    """Recursively find all latencyMs values in the JSON tree."""
    latencies = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == 'latencyMs' and v is not None:
                latencies.append(v)
            else:
                latencies.extend(find_latencies(v))
    elif isinstance(obj, list):
        for item in obj:
            latencies.extend(find_latencies(item))
    return latencies

try:
    with open('output.json', 'r') as f:
        data = json.load(f)

    # Hunt for the numbers
    all_latencies = find_latencies(data)

    if not all_latencies:
        print("⚠️ No latency data found in output.json.")
        print("Tip: Run the eval command with '--output output.json' again.")
    else:
        avg_lat = np.mean(all_latencies)
        std_dev = np.std(all_latencies)
        # Stability Score: 100 - Coefficient of Variation
        score = max(0, 100 - (std_dev / avg_lat * 100)) if avg_lat > 0 else 0

        print(f"\n" + "="*30)
        print(f" STABILITY NETWORK AUDIT")
        print(f"="*30)
        print(f"Data Points:   {len(all_latencies)}")
        print(f"Avg Latency:   {avg_lat:.2f}ms")
        print(f"Jitter (Std):  {std_dev:.2f}ms")
        print(f"FICO SCORE:    {score:.2f}%")
        print(f"="*30)

except FileNotFoundError:
    print("❌ Error: output.json not found.")
except Exception as e:
    print(f"❌ Analysis Error: {e}")