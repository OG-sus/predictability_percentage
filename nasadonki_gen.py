import os
import requests
import time
import pandas as pd
from dotenv import load_dotenv
from fsr import calculate_predictability  # Adjust if your import path differs

load_dotenv()
API_KEY = os.environ.get("NASA_API_KEY")
if not API_KEY:
    raise RuntimeError("NASA_API_KEY not set. Add it to your .env file.")
HEADERS = {'User-Agent': 'Mozilla/5.0'}

# Break 10 years into 2-year intervals to avoid NASA API 503 timeouts
DATE_RANGES = [
    ("2016-01-01", "2017-12-31"),
    ("2018-01-01", "2019-12-31"),
    ("2020-01-01", "2021-12-31"),
    ("2022-01-01", "2023-12-31"),
    ("2024-01-01", "2026-09-01"),
]

kp_series = []
print("Fetching NASA DONKI Geomagnetic Storm data in chunks...")

for start_date, end_date in DATE_RANGES:
    url = f"https://api.nasa.gov/DONKI/GST?startDate={start_date}&endDate={end_date}&api_key={API_KEY}"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            chunk_count = 0
            for event in data:
                if "allKpIndex" in event and event["allKpIndex"]:
                    for kp_entry in event["allKpIndex"]:
                        if "kpIndex" in kp_entry:
                            kp_series.append(float(kp_entry["kpIndex"]))
                            chunk_count += 1
            print(f"  ✓ Processed {start_date} to {end_date}: +{chunk_count} Kp records")
        else:
            print(f"  ✕ Range {start_date} to {end_date} failed: HTTP {resp.status_code}")
    except Exception as e:
        print(f"  ✕ Request error: {e}")
    
    time.sleep(1) # Prevent rate-limiting

print(f"\nTotal Retrieved: {len(kp_series)} Kp Index observations.")

if kp_series:
    print("\nRecent 20 Kp Values:", kp_series[-20:])
    score = calculate_predictability(kp_series, k=0.5)
    print(f"\nOverall Kp Index Predictability Score: {score:.2f}%")
    print("\n--- COPY DATA BELOW FOR YOUR DASHBOARD ---")
    print(", ".join(map(str, kp_series)))