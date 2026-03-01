import numpy as np
import matplotlib.pyplot as plt
from fsr import calculate_predictability

def generate_bridge_data():
    """
    Simulates sensor data from a bridge structure.
    Phase 1: Healthy (Clean Sine Wave)
    Phase 2: Micro-Fractures (Sine Wave + Noise)
    Phase 3: Structural Failure (Chaos)
    """
    print("--- Generating Bridge Stress Sensor Data ---")

    # Phase 1: Healthy (50 hours)
    t1 = np.linspace(0, 10, 50)
    phase1 = 10 + 2 * np.sin(t1) # Base load 10, oscillation +/- 2
    
    # Phase 2: Micro-Fractures (30 hours) - Adding subtle noise
    t2 = np.linspace(10, 16, 30)
    noise2 = np.random.normal(0, 0.5, 30) # Small random noise
    phase2 = 10 + 2 * np.sin(t2) + noise2

    # Phase 3: Failure (20 hours) - Massive variance
    t3 = np.linspace(16, 20, 20)
    noise3 = np.random.normal(0, 5.0, 20) # Huge noise
    phase3 = 10 + 2 * np.sin(t3) + noise3

    # Combine
    full_data = np.concatenate([phase1, phase2, phase3])
    
    # Round to 2 decimals for cleaner output
    full_data = np.round(full_data, 2)
    
    print(f"\nTotal Data Points: {len(full_data)}")
    print("\n--- Phase 1: Healthy (First 10 points) ---")
    print(list(full_data[:10]))
    
    print("\n--- Phase 2: Micro-Fractures (Middle 10 points) ---")
    print(list(full_data[50:60]))
    
    print("\n--- Phase 3: Failure (Last 10 points) ---")
    print(list(full_data[-10:]))

    # Calculate Scores for each phase
    score1 = calculate_predictability(phase1, k=15.0)
    score2 = calculate_predictability(phase2, k=15.0)
    score3 = calculate_predictability(phase3, k=15.0)

    print("\n--- Predictability Scores (k=15.0 - Safety Mode) ---")
    print(f"Phase 1 (Healthy):        {score1:.2f}% (Baseline)")
    print(f"Phase 2 (Micro-Fracture): {score2:.2f}% (WARNING: Drift Detected)")
    print(f"Phase 3 (Failure):        {score3:.2f}% (CRITICAL FAILURE)")
    
    print("\n--- Copy this data for your Dashboard ---")
    print(", ".join(map(str, full_data)))

if __name__ == "__main__":
    generate_bridge_data()
