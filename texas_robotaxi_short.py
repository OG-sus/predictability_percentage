#!/usr/bin/env python3
"""Texas Robotaxi Race — Tesla vs Waymo fleet size, Shorts chart (1080x1920).

Live data every run: daily fleet counts from the TxDMV Automated Vehicle
Registry via texasavtracker.com (see texas_av_gen.py), tracked since
2026-05-28. Counts are REGISTERED vehicles statewide - say "registered",
not "deployed" (same-day jumps across both companies, e.g. 2026-09-02,
look like DMV batch processing).

Run:
    python texas_robotaxi_short.py
"""
from datetime import date, datetime, timezone

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.offsetbox import AnnotationBbox, OffsetImage

from fsr import calculate_predictability
from texas_av_gen import daily_series, fetch, model_breakdown

SHORTS_W_IN, SHORTS_H_IN, DPI = 9, 16, 120
LOGO_PATH = "stream_infra/brand_logo.png"
SAFE_LEFT, SAFE_RIGHT = 0.075, 0.80
SAFE_TOP, SAFE_BOTTOM = 0.88, 0.205
K = 2.0

BG, PANEL, GRID = '#080810', '#0e0e1a', '#1a1a2e'
TESLA_C, WAYMO_C = '#e82127', '#00e0c6'   # Tesla red, Waymo teal
TEXT, DIM, WHITE = '#d4d4e8', '#5a5a7a', '#f0f0ff'

today = datetime.now(timezone.utc).date()
fleets = {}
for brand in ("tesla", "waymo"):
    data = fetch(brand)
    dates, series = daily_series(data["history"], today)
    fleets[brand] = {
        "dates": [date.fromisoformat(d) for d in dates], "series": series,
        "score": calculate_predictability(series, K), "data": data,
    }
t, w = fleets["tesla"], fleets["waymo"]
cybercab = model_breakdown(t["data"]).get("Cybercab")  # (count, first-registered date)

fig = plt.figure(figsize=(SHORTS_W_IN, SHORTS_H_IN), facecolor=BG, dpi=DPI)
ax = fig.add_axes([SAFE_LEFT + 0.09, SAFE_BOTTOM + 0.02, SAFE_RIGHT - (SAFE_LEFT + 0.09) - 0.01, 0.49])
ax.set_facecolor(PANEL)

for f, color, label in ((w, WAYMO_C, "Waymo"), (t, TESLA_C, "Tesla")):
    ax.plot(f["dates"], f["series"], color=color, linewidth=3.2, label=f"{label}  ({f['score']:.0f}% stable)")
    ax.fill_between(f["dates"], f["series"], 0, color=color, alpha=0.08)
ax.set_xlim(t["dates"][0], t["dates"][-1])
ax.set_ylim(0, max(w["series"]) * 1.18)

# Growth callouts, pulled left of the last point so they stay out of the Shorts UI column.
ax.annotate(f"{w['series'][-1]:,}\nx{w['series'][-1] / w['series'][0]:.1f}",
            xy=(w["dates"][-1], w["series"][-1]), xytext=(-60, 18), textcoords='offset points',
            color=WHITE, fontsize=13, fontweight='bold', ha='center',
            arrowprops=dict(arrowstyle='->', color=WAYMO_C, lw=2))
ax.annotate(f"{t['series'][-1]:,}\nx{t['series'][-1] / t['series'][0]:.1f}",
            xy=(t["dates"][-1], t["series"][-1]), xytext=(-60, -70), textcoords='offset points',
            color=WHITE, fontsize=13, fontweight='bold', ha='center',
            arrowprops=dict(arrowstyle='->', color=TESLA_C, lw=2))
ax.text(t["dates"][0], t["series"][0] + 35, f"Tesla: {t['series'][0]}", color=TESLA_C, fontsize=11, fontweight='bold')
ax.text(w["dates"][0], w["series"][0] + 35, f"Waymo: {w['series'][0]}", color=WAYMO_C, fontsize=11, fontweight='bold')

if cybercab:
    cc_date = date.fromisoformat(cybercab[1])
    ax.axvline(cc_date, color=TESLA_C, linestyle=':', linewidth=1.6, alpha=0.8)
    ax.text(cc_date, ax.get_ylim()[1] * 0.97, " Cybercabs\n arrive", color=TESLA_C, fontsize=10,
            fontweight='bold', ha='right', va='top')

ax.legend(loc='upper left', facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=12)

try:
    logo = OffsetImage(plt.imread(LOGO_PATH), zoom=0.16)
    fig.add_artist(AnnotationBbox(logo, (SAFE_RIGHT - 0.08, SAFE_TOP - 0.025),
                                  xycoords='figure fraction', frameon=False, zorder=10))
except FileNotFoundError:
    pass

ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
ax.tick_params(colors=TEXT, labelsize=9, rotation=45)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:,.0f}'))
for spine in ax.spines.values():
    spine.set_color(GRID)
ax.grid(True, color=GRID, linewidth=0.6, alpha=0.6)

fig.text(SAFE_LEFT, SAFE_TOP - 0.035, "TESLA vs WAYMO", color=WHITE, fontsize=27, fontweight='bold')
fig.text(SAFE_LEFT, SAFE_TOP - 0.068, f"Robotaxis registered in Texas  —  {t['dates'][0]:%b %d} to {t['dates'][-1]:%b %d}",
         color=TEXT, fontsize=13)
fig.text(SAFE_LEFT, SAFE_TOP - 0.105, f"Tesla {t['score']:.0f}%  vs  Waymo {w['score']:.0f}%  stability (k={K})",
         color=TESLA_C, fontsize=17, fontweight='bold')
fig.text(SAFE_LEFT, SAFE_TOP - 0.132, "Data: TxDMV AV Registry via texasavtracker.com", color=DIM, fontsize=11)
fig.text(SAFE_LEFT, SAFE_BOTTOM - 0.025, "predictability-api.com", color=DIM, fontsize=12, fontweight='bold')

plt.savefig("texas_robotaxi_short.png", dpi=DPI, facecolor=BG)
print("Saved texas_robotaxi_short.png (1080x1920, Shorts-ready)")
for name, f in (("Tesla", t), ("Waymo", w)):
    print(f"{name}: {f['series'][0]:,} -> {f['series'][-1]:,} (x{f['series'][-1] / f['series'][0]:.1f}), "
          f"score {f['score']:.1f}%")
if cybercab:
    print(f"Cybercabs: {cybercab[0]} registered, first on {cybercab[1]}")
