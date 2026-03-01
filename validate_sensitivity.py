import math
import pandas as pd  # standard for data handling

def calculate_predictability(mean, std_dev, k):
    """
    Calculates consistency score based on CoV and Euler's decay.
    Formula: P = 100 * e^(-k * CoV)
    """
    if mean == 0: return 0.0
    cov = std_dev / mean
    score = 100 * math.exp(-k * cov)
    return round(score, 2)

# 1. Simulate a single dataset (e.g., a set of data with 15% variance)
# Mean = 100, StD = 15 -> CoV = 0.15
current_mean = 100
current_std = 15 

# 2. Define your "Sensitivity Map" (The K factors)
sensitivity_map = {
    "Pharma (Strict)": 15.0,
    "Alloy (High Safety)": 8.0,
    "Finance (Moderate)": 2.0,
    "Fantasy Sports (Lenient)": 0.5
}

# 3. Run the Comparison
results = []
print(f"--- Testing Data with 15% Variance (CoV: 0.15) ---\n")

for industry, k_value in sensitivity_map.items():
    score = calculate_predictability(current_mean, current_std, k_value)
    
    # Add a status label for context
    status = "Consistent" if score > 75 else "Volatile"
    
    results.append({
        "Industry": industry,
        "K-Factor": k_value,
        "Score": f"{score}%",
        "Verdict": status
    })
    print(f"Industry: {industry:<25} | K: {k_value:<4} | Score: {score}%")

# Optional: Create a DataFrame if you want to export to CSV later
df = pd.DataFrame(results)
