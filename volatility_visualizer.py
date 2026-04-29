import matplotlib.pyplot as plt
import numpy as np

# --- 1. DATA INPUT ---
# Simulated Nvidia B200 Price Action (Feb to April 2026)
days = np.arange(1, 21)
prices = [32000, 32500, 31800, 33000, 34500, 38000, 42000, 41500, 43000, 45000, 
          44000, 46500, 48000, 47500, 49000, 52000, 51000, 53000, 55000, 58000]

# --- 2. CALCULATE BANDS (The FSR Logic) ---
# High volatility = lower Pscore = wider band. 
# We'll simulate a Pscore drop from 92% to 75% due to news.
pscore = 75.0 
k_factor = 2.0 # Strict Fintech/Hardware setting
variance = (100 - pscore) * k_factor * 15 # Scaling for visual impact

upper_band = [p + variance for p in prices]
lower_band = [p - variance for p in prices]

# --- 3. PLOTTING ---
plt.figure(figsize=(12, 6), facecolor='#f8f9fa')
plt.plot(days, prices, color='#0052ff', linewidth=3, label='B200 Market Mean', zorder=3)

# The "Confidence Cloud"
plt.fill_between(days, lower_band, upper_band, color='#0052ff', alpha=0.15, label=f'FSR Stability Band ({pscore}%)')

# Styling
plt.title("NVIDIA Blackwell (B200) Price Stability Index", fontsize=16, fontweight='bold', pad=20)
plt.xlabel("Observation Day (April 2026)", fontsize=12)
plt.ylabel("Price (USD)", fontsize=12)
plt.grid(True, linestyle='--', alpha=0.6)
plt.legend(loc='upper left')

# --- 4. SAVE ---
plt.savefig('b200_volatility_news.png', dpi=300, bbox_inches='tight')
# Add a professional 'Stat Box' to the corner of the graph
text_str = f"FSR Score: {pscore}%"
plt.gca().text(0.95, 0.05, text_str, transform=plt.gca().transAxes,
               fontsize=14, fontweight='bold', color='white',
               bbox=dict(facecolor='#0052ff', alpha=0.8, edgecolor='none', pad=10),
               verticalalignment='bottom', horizontalalignment='right')
print("Graph saved as b200_volatility_news.png")
plt.show()