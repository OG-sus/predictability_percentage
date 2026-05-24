import matplotlib.pyplot as plt
import numpy as np
import random
from sliding_window import calculate_sliding_window

def generate_tennis_match():
    print("Generating synthetic tennis match data...")
    
    rally_lengths = []
    
    # --- Set 1 & 2: High Quality, Consistent (The "Zone") ---
    # Rallies are consistently 4-10 shots.
    for _ in range(100):
        rally_lengths.append(int(np.random.normal(6, 1.5))) # Mean 6, Low Variance

    # --- Set 3: Fatigue Sets In (The "Drift") ---
    # Rallies get shorter on average, but variance increases (some long, some very short)
    for _ in range(50):
        rally_lengths.append(int(np.random.normal(4, 3.0))) # Mean 4, High Variance
        
    # --- Set 4: The Collapse (The "Tilt") ---
    # Player is rushing. Lots of 1-2 shot points (errors/winners).
    for _ in range(50):
        val = int(np.random.normal(2, 4.0))
        rally_lengths.append(max(1, val)) # Ensure at least 1 shot

    # Clean up negative numbers from random generation
    rally_lengths = [max(1, x) for x in rally_lengths]
    
    return rally_lengths

def analyze_simulation():
    # 1. Get Data
    rally_lengths = generate_tennis_match()
    
    print(f"Analyzing {len(rally_lengths)} points...")

    # 2. Run Predictability Engine
    window_size = 15
    k_factor = 0.5  # Sports standard
    results = calculate_sliding_window(rally_lengths, window_size, k=k_factor)
    
    scores = [r['score'] for r in results]
    scores = [None] * (window_size - 1) + scores # Pad for plotting

    # 3. Plot
    plt.figure(figsize=(12, 8))
    
    # Top: Raw Data
    plt.subplot(2, 1, 1)
    plt.plot(rally_lengths, color='#007bff', alpha=0.6, label='Rally Length (Shots)')
    plt.title("Simulated Match: Rally Length Analysis")
    plt.ylabel("Shots")
    plt.axvline(x=100, color='gray', linestyle='--', alpha=0.5, label='Fatigue Starts')
    plt.axvline(x=150, color='gray', linestyle='--', alpha=0.5, label='Collapse')
    plt.legend(loc='upper right')
    plt.grid(True, alpha=0.2)

    # Bottom: Predictability Score
    plt.subplot(2, 1, 2)
    plt.plot(scores, color='#dc3545', linewidth=2, label='Predictability Score')
    plt.axhline(y=60, color='orange', linestyle='--', label='Warning Threshold')
    plt.ylabel("Stability Score (0-100)")
    plt.xlabel("Point Number")
    plt.ylim(0, 100)
    
    # Annotations
    plt.text(20, 90, "Stable Play (Score > 80)", color='green', fontweight='bold')
    plt.text(110, 40, "Drift Detected", color='orange', fontweight='bold')
    plt.text(160, 20, "CRITICAL INSTABILITY", color='red', fontweight='bold')
    
    plt.grid(True, alpha=0.2)
    plt.legend(loc='lower left')

    plt.tight_layout()
    plt.savefig("tennis_simulation.png")
    print("Chart saved to 'tennis_simulation.png'")

if __name__ == "__main__":
    analyze_simulation()
