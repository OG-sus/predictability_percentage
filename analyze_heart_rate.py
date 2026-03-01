import csv
import os
from sliding_window import calculate_sliding_window

def analyze_heart_rate():
    # Path to the file you are currently editing
    file_path = os.path.join("Business_Assets_To_Move", "heart_rate_simulation.csv")
    
    # 1. Read the CSV data
    heart_rates = []
    timestamps = []
    try:
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                heart_rates.append(float(row['HeartRate']))
                timestamps.append(row['Time'])
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return

    print(f"Loaded {len(heart_rates)} data points.")

    # 2. Run Sliding Window Analysis
    # Using k=2.0 (Finance/Strict) to detect the arrhythmia/instability clearly.
    # Normal HR variance is fine, but we want to catch the spikes.
    
    WINDOW_SIZE = 10
    K_FACTOR = 2.0
    
    print(f"Running analysis with Window={WINDOW_SIZE}, K={K_FACTOR}...")
    results = calculate_sliding_window(heart_rates, WINDOW_SIZE, k=K_FACTOR)

    # 3. Print Results
    print("\n--- Analysis Results ---")
    print(f"{'Time':<10} {'Avg HR':<10} {'Score':<10} {'Status'}")
    print("-" * 50)

    for res in results:
        window_data = res['data']
        avg_hr = sum(window_data) / len(window_data)
        score = res['score']
        start_idx = res['window_start']
        
        # Determine status label for display
        if score > 90: status = "STABLE"
        elif score > 60: status = "DRIFTING"
        else: status = "UNSTABLE"

        # Print if unstable or periodically
        if score < 60 or start_idx % 10 == 0:
             # Use the timestamp from the start of the window
             t_val = timestamps[start_idx-1]
             print(f"{t_val:<10} {avg_hr:<10.1f} {score:<10.1f} {status}")

if __name__ == "__main__":
    analyze_heart_rate()
