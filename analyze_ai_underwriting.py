import matplotlib.pyplot as plt
import numpy as np
import random
import os
from sliding_window import calculate_sliding_window

def generate_ai_scores():
    print("Generating synthetic AI Underwriting data...")
    
    scores = []
    
    # --- Phase 1: Stable Operation (0-100 applicants) ---
    # The AI is processing a batch of "Standard" applicants.
    # Most scores are around 75, with small variations.
    # This represents a "Predictable" stream of business.
    for _ in range(100):
        val = np.random.normal(75, 5.0) # Mean 75, Low Variance
        scores.append(max(0, min(100, val)))

    # --- Phase 2: Model Drift / Chaos (100-150 applicants) ---
    # Something breaks. The AI starts outputting random garbage.
    # Scores jump from 20 to 90 to 10.
    # This is "High Volatility" = "Low Predictability".
    for _ in range(50):
        val = np.random.normal(50, 30.0) # Huge Variance
        scores.append(max(0, min(100, val)))

    return scores

def analyze_simulation():
    # 1. Get Data
    ai_scores = generate_ai_scores()
    
    print(f"Analyzing {len(ai_scores)} loan applications...")

    # 2. Run Predictability Engine
    window_size = 20
    k_factor = 1.0
    results = calculate_sliding_window(ai_scores, window_size, k=k_factor)
    
    predictability_scores = [r['score'] for r in results]
    predictability_scores = [None] * (window_size - 1) + predictability_scores # Pad

    # 3. Plot
    plt.figure(figsize=(12, 8))
    
    # Top: Raw AI Scores
    plt.subplot(2, 1, 1)
    plt.plot(ai_scores, color='#6f42c1', alpha=0.6, label='AI Confidence Score (0-100)')
    plt.title("AI Underwriting Model: Confidence Scores")
    plt.ylabel("Score")
    plt.axvline(x=100, color='gray', linestyle='--', alpha=0.5, label='Drift Starts')
    plt.legend(loc='upper right')
    plt.grid(True, alpha=0.2)

    # Bottom: Predictability Score
    plt.subplot(2, 1, 2)
    plt.plot(predictability_scores, color='#dc3545', linewidth=2, label='Model Stability Score')
    plt.axhline(y=60, color='orange', linestyle='--', label='Alert Threshold')
    plt.ylabel("Stability (0-100)")
    plt.xlabel("Application Number")
    plt.ylim(0, 100)
    
    # Annotations
    plt.text(10, 85, "Stable Operation", color='green', fontweight='bold')
    plt.text(110, 20, "MODEL FAILURE DETECTED", color='red', fontweight='bold')
    
    plt.grid(True, alpha=0.2)
    plt.legend(loc='lower left')

    plt.tight_layout()
    output_dir = os.path.join("static", "images")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "ai_underwriting_analysis.png")
    plt.savefig(output_path)
    print(f"Chart saved to '{output_path}'")

if __name__ == "__main__":
    analyze_simulation()
