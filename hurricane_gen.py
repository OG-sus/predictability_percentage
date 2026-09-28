"""
hurricane_gen.py — Atlantic Hurricane Season FSR
=================================================
NOAA historical storm data (1980-2025), 2-panel YouTube chart.
Left: bar chart with rolling FSR overlay.
Right: score card.

Live mode: any active storm's 6-hourly NHC best track (wind + pressure),
scored with a 24-hour sliding window, printed for the website calculator.

Usage:
    python hurricane_gen.py                    # season chart, 1980-2025
    python hurricane_gen.py --active           # list storms active right now
    python hurricane_gen.py --storm Polo       # one storm's track + rapid intensification
    python hurricane_gen.py --storm ep172026 --csv   # by NHC id, save CSV
"""

import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker
from matplotlib.patches import FancyBboxPatch
from datetime import datetime

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

# ── DATA: NOAA Atlantic Basin Annual Summary 1980-2025 ────────────────────────
# Source: NOAA/NHC historical records (public domain)
# Columns: year, named_storms, hurricanes, major_hurricanes (Cat 3+)
NOAA_DATA = [
    (1980, 11, 9, 2), (1981, 12, 7, 3), (1982,  6, 2, 1), (1983,  4, 3, 1),
    (1984, 12, 5, 1), (1985, 11, 7, 3), (1986,  6, 4, 0), (1987,  7, 3, 1),
    (1988, 12, 5, 3), (1989, 11, 7, 2), (1990, 14, 8, 1), (1991,  8, 4, 2),
    (1992,  7, 4, 1), (1993,  8, 4, 1), (1994,  7, 3, 0), (1995, 19,11, 5),
    (1996, 13, 9, 6), (1997,  8, 3, 1), (1998, 14,10, 3), (1999, 12, 8, 5),
    (2000, 15, 8, 3), (2001, 15, 9, 4), (2002, 12, 4, 2), (2003, 16, 7, 3),
    (2004, 15, 9, 6), (2005, 28,15, 7), (2006, 10, 5, 2), (2007, 15, 6, 2),
    (2008, 16, 8, 5), (2009,  9, 3, 2), (2010, 19,12, 5), (2011, 19, 7, 4),
    (2012, 19,10, 2), (2013,  2, 2, 0), (2014,  8, 6, 2), (2015, 11, 4, 2),
    (2016, 15, 7, 4), (2017, 17,10, 6), (2018, 15, 8, 2), (2019, 18, 6, 3),
    (2020, 30,14, 7), (2021, 21, 7, 4), (2022, 14, 7, 2), (2023, 20, 7, 3),
    (2024, 18,11, 5), (2025, 13, 5, 4),   # 2025: NOAA season recap (3 Cat 5s)
]

YEARS          = [r[0] for r in NOAA_DATA]
NAMED_STORMS   = [r[1] for r in NOAA_DATA]
HURRICANES     = [r[2] for r in NOAA_DATA]
MAJOR          = [r[3] for r in NOAA_DATA]

K      = 1.0
WINDOW = 10       # 10-year rolling FSR
OUT    = "hurricane_gen.png"

# ── PALETTE ───────────────────────────────────────────────────────────────────
BG    = '#080810'
PANEL = '#0d0d1c'
GRID  = '#1a1a2e'
TEXT  = '#d4d4f0'
DIM   = '#5a5a8a'
WHITE = '#f0f0ff'
GREEN = '#00e676'
GOLD  = '#ffca28'
RED   = '#ff5252'

C_NAMED = '#29b6f6'   # blue
C_HURR  = '#ef5350'   # red
C_MAJOR = '#ffca28'   # gold

# ── HELPERS ───────────────────────────────────────────────────────────────────
def score_color(s):
    if s >= 70: return GREEN
    if s >= 45: return GOLD
    return RED

def score_label(s):
    if s >= 70: return 'PREDICTABLE'
    if s >= 45: return 'MODERATE'
    return 'VOLATILE'

def style_ax(ax):
    ax.set_facecolor(PANEL)
    for sp in ax.spines.values():
        sp.set_edgecolor(GRID)
    ax.tick_params(colors=TEXT, labelsize=10)
    ax.grid(axis='y', color=GRID, linewidth=0.5, alpha=0.7)
    ax.grid(axis='x', visible=False)

# ── CHART ─────────────────────────────────────────────────────────────────────
def build_chart():
    # Compute overall FSR scores
    s_named = calculate_predictability(NAMED_STORMS, k=K)
    s_hurr  = calculate_predictability(HURRICANES,   k=K)
    s_major = calculate_predictability(MAJOR,        k=K)

    # Rolling FSR (10-year window)
    sw_named = calculate_sliding_window(NAMED_STORMS, WINDOW, k=K)
    sw_hurr  = calculate_sliding_window(HURRICANES,   WINDOW, k=K)
    sw_major = calculate_sliding_window(MAJOR,        WINDOW, k=K)

    roll_x     = YEARS[WINDOW - 1:]
    roll_named = [r['score'] for r in sw_named]
    roll_hurr  = [r['score'] for r in sw_hurr]
    roll_major = [r['score'] for r in sw_major]

    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    fig.patch.set_facecolor(BG)

    gs = gridspec.GridSpec(
        2, 2,
        width_ratios=[3.2, 1],
        height_ratios=[1.6, 1],
        hspace=0.38, wspace=0.22,
        left=0.06, right=0.97,
        top=0.87, bottom=0.07,
    )

    ax_bars  = fig.add_subplot(gs[0, 0])   # annual storm counts
    ax_fsr   = fig.add_subplot(gs[1, 0])   # rolling FSR
    ax_score = fig.add_subplot(gs[:, 1])   # score card (full height)

    for ax in [ax_bars, ax_fsr, ax_score]:
        style_ax(ax)

    xs = np.arange(len(YEARS))
    w  = 0.28

    # ── BAR CHART ─────────────────────────────────────────────────────────────
    ax_bars.bar(xs - w,   NAMED_STORMS, w, color=C_NAMED, alpha=0.85, label='Named Storms',     zorder=3)
    ax_bars.bar(xs,       HURRICANES,   w, color=C_HURR,  alpha=0.85, label='Hurricanes',        zorder=3)
    ax_bars.bar(xs + w,   MAJOR,        w, color=C_MAJOR, alpha=0.85, label='Major (Cat 3+)',    zorder=3)

    # Notable seasons annotation
    notable = {2005: 'Katrina', 2017: 'Harvey/Irma', 2020: 'Record 30'}
    for yr, lbl in notable.items():
        if yr in YEARS:
            i = YEARS.index(yr)
            val = NAMED_STORMS[i]
            ax_bars.text(xs[i] - w, val + 0.6, lbl, color=WHITE, fontsize=7.5,
                         ha='center', va='bottom', fontfamily='monospace', alpha=0.8,
                         rotation=0)

    # Season average line
    avg_named = sum(NAMED_STORMS) / len(NAMED_STORMS)
    ax_bars.axhline(avg_named, color=C_NAMED, linewidth=1.0, linestyle='--', alpha=0.4)
    ax_bars.text(len(YEARS) - 0.3, avg_named + 0.4,
                 f'avg {avg_named:.1f}', color=C_NAMED, fontsize=8,
                 fontfamily='monospace', alpha=0.6, ha='right')

    ax_bars.set_xticks(xs[::3])
    ax_bars.set_xticklabels([str(YEARS[i]) for i in range(0, len(YEARS), 3)],
                             fontfamily='monospace', fontsize=9)
    ax_bars.set_xlim(-0.8, len(YEARS) - 0.2)
    ax_bars.set_ylim(0, 36)
    ax_bars.set_ylabel('Storms Per Season', color=TEXT, fontsize=10, fontfamily='monospace')
    ax_bars.set_title(f'Atlantic Hurricane Season — Annual Activity ({YEARS[0]}–{YEARS[-1]})',
                      color=WHITE, fontsize=13, fontfamily='monospace', pad=10)

    leg = ax_bars.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
                         fontsize=10, loc='upper left', handlelength=1.6)
    for t in leg.get_texts():
        t.set_fontfamily('monospace')

    # ── ROLLING FSR ───────────────────────────────────────────────────────────
    roll_xs = np.arange(WINDOW - 1, len(YEARS))

    for ys, color, label, score in [
        (roll_named, C_NAMED, f'Named Storms  {s_named:.1f}', s_named),
        (roll_hurr,  C_HURR,  f'Hurricanes      {s_hurr:.1f}', s_hurr),
        (roll_major, C_MAJOR, f'Major (Cat3+)  {s_major:.1f}', s_major),
    ]:
        ax_fsr.fill_between(roll_xs, ys, alpha=0.08, color=color)
        ax_fsr.plot(roll_xs, ys, color=color, linewidth=2.0, label=label)
        ax_fsr.scatter([roll_xs[-1]], [ys[-1]], color=color, s=55,
                       zorder=5, edgecolors=BG, linewidths=1.5)
        ax_fsr.text(roll_xs[-1] + 0.3, ys[-1], f'{ys[-1]:.0f}',
                    color=color, fontsize=9, va='center', fontfamily='monospace')

    ax_fsr.axhline(70, color=GREEN, linewidth=0.8, linestyle=':', alpha=0.5)
    ax_fsr.axhline(45, color=GOLD,  linewidth=0.8, linestyle=':', alpha=0.5)
    ax_fsr.text(0.2, 71.5, 'PREDICTABLE', color=GREEN, fontsize=8, alpha=0.6,
                fontfamily='monospace')
    ax_fsr.text(0.2, 46.5, 'MODERATE',    color=GOLD,  fontsize=8, alpha=0.6,
                fontfamily='monospace')

    ax_fsr.set_xticks(roll_xs[::3])
    ax_fsr.set_xticklabels([str(YEARS[WINDOW - 1 + i * 3]) for i in range(len(roll_xs[::3]))],
                            fontfamily='monospace', fontsize=9)
    ax_fsr.set_xlim(-0.8, len(YEARS) - 0.2)
    ax_fsr.set_ylim(0, 105)
    ax_fsr.set_ylabel('FSR Score', color=TEXT, fontsize=10, fontfamily='monospace')
    ax_fsr.set_xlabel(f'{WINDOW}-Year Rolling FSR Window  ·  k={K}',
                      color=DIM, fontsize=9, fontfamily='monospace')
    ax_fsr.set_title(f'FSR Predictability Score — {WINDOW}-Year Rolling Window',
                     color=WHITE, fontsize=12, fontfamily='monospace', pad=8)

    leg2 = ax_fsr.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
                          fontsize=10, loc='upper right', handlelength=1.6)
    for t in leg2.get_texts():
        t.set_fontfamily('monospace')

    # ── SCORE CARD ────────────────────────────────────────────────────────────
    ax_score.set_xlim(0, 1)
    ax_score.set_ylim(0, 1)
    ax_score.set_xticks([])
    ax_score.set_yticks([])

    ax_score.text(0.5, 0.975, 'FSR VERDICT', ha='center', va='top',
                  fontsize=11, color=DIM, fontfamily='monospace', fontweight='bold')
    ax_score.text(0.5, 0.935, f'{YEARS[0]} – {YEARS[-1]}', ha='center', va='top',
                  fontsize=9, color=DIM, fontfamily='monospace')

    badges = [
        ('Named Storms', s_named, C_NAMED),
        ('Hurricanes',   s_hurr,  C_HURR),
        ('Major Cat 3+', s_major, C_MAJOR),
    ]
    slot_h  = 0.255
    tops    = [0.88, 0.88 - slot_h, 0.88 - slot_h * 2]

    for (label, score, color), top in zip(badges, tops):
        sc = score_color(score)
        pad = 0.04
        rect = FancyBboxPatch(
            (pad, top - slot_h + pad * 0.5), 1 - pad * 2, slot_h - pad,
            boxstyle='round,pad=0.015',
            facecolor=PANEL, edgecolor=sc, linewidth=2.2, alpha=0.95,
            transform=ax_score.transData, zorder=2,
        )
        ax_score.add_patch(rect)
        mid_y = top - slot_h / 2 + pad * 0.25
        ax_score.text(0.5, mid_y + 0.055, f'{score:.1f}',
                      ha='center', va='center', fontsize=28, fontweight='bold',
                      color=sc, fontfamily='monospace', zorder=3)
        ax_score.text(0.5, mid_y - 0.05, label,
                      ha='center', va='center', fontsize=9, fontweight='bold',
                      color=color, fontfamily='monospace', zorder=3)
        ax_score.text(0.5, mid_y - 0.10, score_label(score),
                      ha='center', va='center', fontsize=8, color=sc,
                      fontfamily='monospace', zorder=3)

    # Season avg stats
    ax_score.text(0.5, 0.025,
                  f'Avg: {avg_named:.1f} named  ·  {sum(HURRICANES)/len(HURRICANES):.1f} hurricanes',
                  ha='center', fontsize=8, color=DIM, fontfamily='monospace')

    # ── HEADER ────────────────────────────────────────────────────────────────
    fig.text(0.5, 0.962,
             'ATLANTIC HURRICANE SEASON  —  IS IT PREDICTABLE?',
             ha='center', fontsize=20, fontweight='bold',
             color=WHITE, fontfamily='monospace')
    fig.text(0.5, 0.930,
             'Named Storms  ·  Hurricanes  ·  Major (Cat 3+)  ·  FSR Predictability Score™  '
             '·  Data: NOAA/NHC  ·  Season starts June 1',
             ha='center', fontsize=10, color=DIM, fontfamily='monospace')

    ts = datetime.now().strftime('%Y-%m-%d')
    fig.text(0.97, 0.012,
             f'Data: NOAA National Hurricane Center  ·  {ts}  ·  predictability-api.com',
             ha='right', fontsize=7.5, color='#2a2a45', fontfamily='monospace')

    plt.savefig(OUT, dpi=100, facecolor=BG, bbox_inches='tight')
    print(f'Saved: {OUT}')
    plt.show()

# ── LIVE STORMS (NHC) ─────────────────────────────────────────────────────────
NHC_CURRENT = "https://www.nhc.noaa.gov/CurrentStorms.json"
NHC_BTK     = "https://ftp.nhc.noaa.gov/atcf/btk/b{id}.dat"   # best track, updated every 6 h
RI_KT_24H   = 30   # NHC's rapid-intensification threshold: +30 kt in 24 h
STORM_WINDOW = 4   # 4 six-hourly points = 24-hour sliding window


def _get(url):
    import requests
    resp = requests.get(url, headers={"User-Agent": "predictability-api.com FSR script"}, timeout=30)
    resp.raise_for_status()
    return resp


def active_storms():
    return _get(NHC_CURRENT).json().get("activeStorms", [])


def print_active():
    storms = active_storms()
    if not storms:
        print("No active storms right now.")
        return
    print(f"\n{len(storms)} active storm(s):\n")
    for s in storms:
        mph = round(int(s["intensity"]) * 1.15078)
        print(f"  {s['name']:<12} {s['classification']:<3} {s['intensity']:>4} kt ({mph} mph)  "
              f"{s['pressure']} mb  id={s['id']}  updated {s['lastUpdate'][:16]}Z")
    print("\nDig into one with: python hurricane_gen.py --storm <name or id>")


def storm_track(name_or_id):
    """6-hourly best track for an active storm (by name) or any NHC id like ep172026."""
    key = name_or_id.lower()
    storm_id = key if key[:2] in ("al", "ep", "cp") and key[2:].isdigit() else None
    if storm_id is None:
        match = [s for s in active_storms() if s["name"].lower() == key]
        if not match:
            raise SystemExit(f"No active storm named '{name_or_id}' - try --active, or pass an id like ep172026.")
        storm_id = match[0]["id"]
    points = {}
    for line in _get(NHC_BTK.format(id=storm_id)).text.splitlines():
        f = [x.strip() for x in line.split(",")]
        # b-deck repeats each time for every wind-radii row; keep one per timestamp
        if len(f) > 10 and f[8]:
            points[f[2]] = (int(f[8]), int(f[9]) if f[9] else None, f[10])
    times = sorted(points)
    return storm_id, times, points


def run_storm(name_or_id, save_csv):
    storm_id, times, pts = storm_track(name_or_id)
    wind = [pts[t][0] for t in times]
    pres = [pts[t][1] for t in times]
    stamp = lambda t: f"{t[:4]}-{t[4:6]}-{t[6:8]} {t[8:10]}Z"

    peak = wind.index(max(wind))
    low_p = pres.index(min(p for p in pres if p))
    print(f"\n{storm_id.upper()}: {len(times)} six-hourly points, {stamp(times[0])} -> {stamp(times[-1])}")
    print(f"  Latest: {wind[-1]} kt ({round(wind[-1] * 1.15078)} mph), {pres[-1]} mb, type {pts[times[-1]][2]}")
    print(f"  Peak wind: {wind[peak]} kt ({round(wind[peak] * 1.15078)} mph) at {stamp(times[peak])}")
    print(f"  Lowest pressure: {pres[low_p]} mb at {stamp(times[low_p])}")

    if len(wind) > 4:
        gains = [(wind[i] - wind[i - 4], i) for i in range(4, len(wind))]
        best, i = max(gains)
        print(f"  Biggest 24h gain: +{best} kt ({wind[i - 4]} -> {wind[i]}) ending {stamp(times[i])}"
              + (f"  = {best / RI_KT_24H:.1f}x the rapid-intensification threshold" if best >= RI_KT_24H else ""))

    if len(wind) >= STORM_WINDOW:
        sw = [r["score"] for r in calculate_sliding_window(wind, STORM_WINDOW, k=K)]
        low = sw.index(min(sw))
        print(f"  24h stability (k={K}): start {sw[0]:.0f}%, lowest {sw[low]:.0f}% "
              f"(window ending {stamp(times[low + STORM_WINDOW - 1])}), latest {sw[-1]:.0f}%")

    print("\n--- Wind, knots (copy for a chart; window 4 = 24 h) ---")
    print(", ".join(map(str, wind)))
    print("\n--- Pressure, mb ---")
    print(", ".join(str(p) for p in pres))

    if save_csv:
        import csv
        path = f"{storm_id}_track.csv"
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["time_utc", "wind_kt", "pressure_mb", "type"])
            w.writerows((stamp(t), pts[t][0], pts[t][1], pts[t][2]) for t in times)
        print(f"\nSaved {path}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Hurricane FSR: season history chart, or a live storm's track")
    parser.add_argument("--active", action="store_true", help="list storms active right now (NHC)")
    parser.add_argument("--storm", metavar="NAME_OR_ID", help="one storm's 6-hourly track, e.g. Polo or ep172026")
    parser.add_argument("--csv", action="store_true", help="with --storm: save <id>_track.csv")
    args = parser.parse_args()
    if args.active:
        print_active()
        raise SystemExit
    if args.storm:
        run_storm(args.storm, args.csv)
        raise SystemExit

    print('Hurricane Season FSR — YouTube Chart')
    print('=' * 40)

    s_named = calculate_predictability(NAMED_STORMS, k=K)
    s_hurr  = calculate_predictability(HURRICANES,   k=K)
    s_major = calculate_predictability(MAJOR,        k=K)

    print(f'  Named Storms  FSR: {s_named:.1f}  [{score_label(s_named)}]')
    print(f'  Hurricanes    FSR: {s_hurr:.1f}  [{score_label(s_hurr)}]')
    print(f'  Major Cat3+   FSR: {s_major:.1f}  [{score_label(s_major)}]')
    print()
    print('Building chart...')
    build_chart()
