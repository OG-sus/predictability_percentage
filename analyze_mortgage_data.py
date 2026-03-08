import pandas as pd
from sliding_window import calculate_sliding_window
import matplotlib.pyplot as plt
import os

def analyze_mortgage_rates():
    """
    Analyzes the stability of 30-year fixed mortgage rates over time.
    """
    # --- 1. Load the Data ---
    try:
        # FRED CSV uses 'observation_date' as the column name
        df = pd.read_csv('MORTGAGE30US.csv', parse_dates=['observation_date'])
    except FileNotFoundError:
        print("ERROR: MORTGAGE30US.csv not found. Please download it from FRED and place it in the project directory.")
        return
    except ValueError as e:
        # Fallback if column names are different
        print(f"CSV Format Error: {e}")
        print("Attempting to load without header...")
        df = pd.read_csv('MORTGAGE30US.csv', header=0, names=['observation_date', 'MORTGAGE30US'], parse_dates=['observation_date'])

    # --- 2. Prepare the Data ---
    # Rename for clarity
    df.rename(columns={'MORTGAGE30US': 'Rate', 'observation_date': 'Date'}, inplace=True)
    
    # FRED data uses '.' for missing values. We need to handle that.
    df['Rate'] = pd.to_numeric(df['Rate'], errors='coerce')
    df.dropna(subset=['Rate'], inplace=True)

    print(f"Loaded {len(df)} data points from {df['Date'].min().year} to {df['Date'].max().year}.")

    # --- 3. Run the Analysis ---
    # We'll use a 52-week (1 year) sliding window to see yearly stability.
    window_size = 52 
    
    # Use a higher K-Factor for finance to be sensitive to volatility
    k_factor = 2.0

    print(f"Running sliding window analysis with window_size={window_size} and k={k_factor}...")
    stability_results = calculate_sliding_window(df['Rate'].tolist(), window_size, k=k_factor)

    # Convert results to a DataFrame for easier plotting
    results_df = pd.DataFrame(stability_results)
    
    # Map window end index back to dates
    # We need to align the results with the original dataframe
    # The sliding window result at index i corresponds to the window ending at df index i + window_size - 1
    
    # Create a list of dates corresponding to the end of each window
    window_end_dates = []
    for res in stability_results:
        end_idx = res['window_end'] - 1 # 0-based index
        if end_idx < len(df):
            window_end_dates.append(df['Date'].iloc[end_idx])
        else:
            window_end_dates.append(None)
            
    results_df['Date'] = window_end_dates
    results_df.dropna(subset=['Date'], inplace=True)

    # --- 4. Visualize the Results ---
    fig, ax1 = plt.subplots(figsize=(14, 7))

    # Plot 1: The actual mortgage rates
    ax1.plot(df['Date'], df['Rate'], color='lightblue', label='30-Year Fixed Rate')
    ax1.set_xlabel('Year')
    ax1.set_ylabel('Mortgage Rate (%)', color='lightblue')
    ax1.tick_params(axis='y', labelcolor='lightblue')
    ax1.grid(True, alpha=0.2)

    # Plot 2: The stability score on a second y-axis
    ax2 = ax1.twinx()
    ax2.plot(results_df['Date'], results_df['score'], color='red', linewidth=2, label='Predictability Score (1-Year Window)')
    ax2.set_ylabel('Predictability Score (0-100)', color='red')
    ax2.tick_params(axis='y', labelcolor='red')
    ax2.set_ylim(0, 105) # Score is 0-100

    # Highlight the 2022 crash
    crash_start = pd.to_datetime('2022-01-01')
    crash_end = pd.to_datetime('2023-06-01')
    ax1.axvspan(crash_start, crash_end, color='red', alpha=0.15, label='2022 Rate Shock')

    plt.title('Predictability of US Mortgage Rates (1971-Present)', fontsize=16, fontweight='bold')
    fig.tight_layout()
    
    # Add a single legend for all plots
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(lines + lines2, labels + labels2, loc='upper left')

    output_dir = os.path.join("static", "images")
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(os.path.join(output_dir, 'mortgage_stability_analysis.png'))
    print(f"\nSUCCESS: Analysis complete. Chart saved to '{os.path.join(output_dir, 'mortgage_stability_analysis.png')}'")
    # plt.show() # Commented out to avoid blocking execution in some environments


if __name__ == "__main__":
    analyze_mortgage_rates()
