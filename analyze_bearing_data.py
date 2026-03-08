import pandas as pd
from sliding_window import calculate_sliding_window
import matplotlib.pyplot as plt
import os
import glob

def analyze_bearing_failure():
    """
    Analyzes NASA bearing vibration data to predict failure.
    Reads directly from the raw data folder.
    """
    # --- 1. Load the Data ---
    # Path to the directory containing the individual test files
    data_dir = r"G:\My Drive\Predictability_API_Business\05_Data_Lab\archive(1)\2nd_test\2nd_test"
    
    print(f"Scanning for data files in: {data_dir}")
    
    # Get all files in the directory, sorted by name (which is the timestamp)
    all_files = sorted(glob.glob(os.path.join(data_dir, "*")))
    
    if not all_files:
        print(f"ERROR: No files found in {data_dir}")
        return

    print(f"Found {len(all_files)} data files. Processing...")

    # We will read each file, take the mean of the absolute vibration for Bearing 1, 
    # and use that as our data point for that time.
    # This creates a time-series of "Vibration Intensity" over the life of the bearing.
    
    timestamps = []
    vibration_levels = []
    
    # Process a subset to keep it fast for the demo (e.g., every 10th file)
    # Or process all if you want the full resolution. Let's do every 5th file for speed.
    step = 5 
    
    for filepath in all_files[::step]:
        try:
            # Filename is the timestamp: 2004.02.12.10.32.39 -> 2004-02-12 10:32:39
            filename = os.path.basename(filepath)
            timestamp = pd.to_datetime(filename, format='%Y.%m.%d.%H.%M.%S')
            
            # Read the file (tab-separated, no header)
            # Columns: Bearing 1, Bearing 2, Bearing 3, Bearing 4
            df = pd.read_csv(filepath, sep='\t', header=None)
            
            # Calculate the mean absolute vibration for Bearing 1 (Column 0)
            # This represents the "energy" of the vibration at this moment
            vibration_intensity = df[0].abs().mean()
            
            timestamps.append(timestamp)
            vibration_levels.append(vibration_intensity)
            
        except Exception as e:
            print(f"Skipping file {filepath}: {e}")
            continue

    print(f"Successfully processed {len(vibration_levels)} time points.")

    # --- 2. Run the Analysis ---
    # Window size: 50 time points (since we are subsampling, this covers a good chunk of time)
    window_size = 50
    
    # K-Factor: 5.0 (High sensitivity for industrial equipment)
    k_factor = 5.0

    print(f"Running sliding window analysis with window_size={window_size} and k={k_factor}...")
    stability_results = calculate_sliding_window(vibration_levels, window_size, k=k_factor)

    # Convert results to DataFrame
    results_df = pd.DataFrame(stability_results)
    
    # Align timestamps
    end_indices = [res['window_end'] - 1 for res in stability_results]
    results_df['Timestamp'] = [timestamps[i] for i in end_indices]
    
    # --- 3. Visualize the Results ---
    fig, ax1 = plt.subplots(figsize=(14, 7))

    # Plot 1: Vibration Intensity
    ax1.plot(timestamps, vibration_levels, color='#007bff', alpha=0.6, label='Vibration Intensity (g)')
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Vibration Level', color='#007bff')
    ax1.tick_params(axis='y', labelcolor='#007bff')
    ax1.set_title('NASA Bearing Failure Prediction', fontsize=16, fontweight='bold')
    ax1.grid(True, alpha=0.2)

    # Plot 2: Predictability Score
    ax2 = ax1.twinx()
    ax2.plot(results_df['Timestamp'], results_df['score'], color='#dc3545', linewidth=2, label='Predictability Score')
    ax2.set_ylabel('Predictability Score (0-100)', color='#dc3545')
    ax2.tick_params(axis='y', labelcolor='#dc3545')
    ax2.set_ylim(0, 105)
    
    # Add a threshold line
    ax2.axhline(y=60, color='orange', linestyle='--', label='Critical Warning Threshold')

    # Combine legends
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(lines + lines2, labels + labels2, loc='upper left')

    fig.tight_layout()

    output_dir = os.path.join("static", "images")
    os.makedirs(output_dir, exist_ok=True)
    output_filename = os.path.join(output_dir, 'bearing_failure_analysis.png')
    plt.savefig(output_filename)
    print(f"\nSUCCESS: Analysis complete. Chart saved to '{output_filename}'")

if __name__ == "__main__":
    analyze_bearing_failure()
