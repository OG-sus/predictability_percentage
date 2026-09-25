#!/usr/bin/env python3
"""bearing_failure_gen.py - "My engine saw this machine breaking 2 days early"

Real sensor data: NASA IMS bearing run-to-failure dataset, test 2 (Bearing 1),
Feb 12-19 2004. Four bearings on a shaft run nonstop until one fails; each file
is a 1-second vibration snapshot taken every 10 minutes. Same processing as
analyze_bearing_data.py (mean |vibration| per snapshot, every 5th file,
50-point sliding window, k=5.0 industrial sensitivity) - but rendered as a
1080x1920 Shorts chart with the warning timeline marked.

Honest framing (checked when this was built): the FSR score dropped below 60
about 51 h before the end of the test, ~38 h before vibration had even doubled.
A plain 3-sigma statistical alarm on this bearing fires a few hours earlier
still, so pitch it as a readable 0-100 stability score that saw it coming,
not as "beats every sensor alarm".

Run:
    python bearing_failure_gen.py
    python bearing_failure_gen.py --data "D:/path/to/2nd_test"   # if the data moves
"""
import argparse
import glob
import os

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.offsetbox import AnnotationBbox, OffsetImage

from sliding_window import calculate_sliding_window

DEFAULT_DATA = r"G:\My Drive\Predictability_API_Business\05_Data_Lab\archive(1)\2nd_test\2nd_test"
STEP, WINDOW, K = 5, 50, 5.0     # identical to analyze_bearing_data.py
WARN = 60                        # the script's "critical warning" line

SHORTS_W_IN, SHORTS_H_IN, DPI = 9, 16, 120
LOGO_PATH = "stream_infra/brand_logo.png"
SAFE_LEFT, SAFE_RIGHT = 0.075, 0.80
SAFE_TOP, SAFE_BOTTOM = 0.88, 0.205

BG, PANEL, GRID = '#080810', '#0e0e1a', '#1a1a2e'
VIB_C, SCORE_C = '#39c2ff', '#ff3d3d'
TEXT, DIM, WHITE, AMBER = '#d4d4e8', '#5a5a7a', '#f0f0ff', '#ffd166'


def load(data_dir):
    files = sorted(glob.glob(os.path.join(data_dir, "*")))
    if not files:
        raise SystemExit(f"No data files in {data_dir} - pass --data with the 2nd_test folder.")
    ts, vib = [], []
    for f in files[::STEP]:
        ts.append(pd.to_datetime(os.path.basename(f), format='%Y.%m.%d.%H.%M.%S'))
        vib.append(pd.read_csv(f, sep='\t', header=None)[0].abs().mean())
    end = pd.to_datetime(os.path.basename(files[-1]), format='%Y.%m.%d.%H.%M.%S')
    return ts, vib, end


def first_sustained(times, flags, n=5):
    """First time a condition holds for n points in a row (ignores one-off blips)."""
    run = 0
    for i, ok in enumerate(flags):
        run = run + 1 if ok else 0
        if run == n:
            return times[i - n + 1]
    return None


def main():
    parser = argparse.ArgumentParser(description="Shorts chart: FSR early warning on NASA bearing failure data")
    parser.add_argument("--data", default=DEFAULT_DATA, help="folder with the IMS 2nd_test files")
    args = parser.parse_args()

    ts, vib, end = load(args.data)
    sw = calculate_sliding_window(vib, WINDOW, k=K)
    sw_t = [ts[r['window_end'] - 1] for r in sw]
    sw_s = [r['score'] for r in sw]

    baseline = sum(vib[:100]) / 100
    warn_t = first_sustained(sw_t, [s < WARN for s in sw_s])
    double_t = first_sustained(ts, [v > 2 * baseline for v in vib])
    hours = lambda t: (end - t).total_seconds() / 3600

    fig = plt.figure(figsize=(SHORTS_W_IN, SHORTS_H_IN), facecolor=BG, dpi=DPI)
    plot_l = SAFE_LEFT + 0.09
    plot_w = SAFE_RIGHT - plot_l - 0.01
    ax_v = fig.add_axes([plot_l, SAFE_BOTTOM + 0.30, plot_w, 0.21])   # vibration
    ax_s = fig.add_axes([plot_l, SAFE_BOTTOM + 0.035, plot_w, 0.21])  # stability score

    ax_v.plot(ts, vib, color=VIB_C, linewidth=2.2)
    ax_v.fill_between(ts, vib, min(vib), color=VIB_C, alpha=0.10)
    ax_v.set_ylabel("Vibration (g)", color=TEXT, fontsize=11)

    ax_s.plot(sw_t, sw_s, color=SCORE_C, linewidth=2.6)
    ax_s.fill_between(sw_t, sw_s, 0, color=SCORE_C, alpha=0.10)
    ax_s.axhline(WARN, color=AMBER, linestyle='--', linewidth=1.3)
    ax_s.text(sw_t[0], WARN + 3, f"warning line ({WARN})", color=AMBER, fontsize=10, fontweight='bold')
    ax_s.set_ylim(0, 105)
    ax_s.set_ylabel("Stability score", color=TEXT, fontsize=11)

    for ax in (ax_v, ax_s):
        ax.set_facecolor(PANEL)
        ax.set_xlim(ts[0], end)
        ax.axvline(end, color=WHITE, linewidth=1.5, alpha=0.8)
        if warn_t is not None:
            ax.axvline(warn_t, color=SCORE_C, linestyle=':', linewidth=2)
        if double_t is not None:
            ax.axvline(double_t, color=VIB_C, linestyle=':', linewidth=2)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
        ax.tick_params(colors=TEXT, labelsize=9)
        for spine in ax.spines.values():
            spine.set_color(GRID)
        ax.grid(True, color=GRID, linewidth=0.6, alpha=0.6)
    ax_v.tick_params(labelbottom=False)

    # Timeline callouts, kept left of the failure line so they stay in the safe box.
    if warn_t is not None:
        ax_s.annotate(f"ENGINE WARNING\n{hours(warn_t):.0f} hours early", xy=(warn_t, WARN),
                      xytext=(-95, -75), textcoords='offset points', color=WHITE, fontsize=12,
                      fontweight='bold', ha='center', arrowprops=dict(arrowstyle='->', color=SCORE_C, lw=2))
    if double_t is not None:
        ax_v.annotate(f"vibration doubles\n{hours(double_t):.0f} hours early", xy=(double_t, 2 * baseline),
                      xytext=(-110, 30), textcoords='offset points', color=WHITE, fontsize=12,
                      fontweight='bold', ha='center', arrowprops=dict(arrowstyle='->', color=VIB_C, lw=2))
    ax_v.text(end, ax_v.get_ylim()[1], "FAILURE ", color=WHITE, fontsize=11, fontweight='bold',
              ha='right', va='top')

    try:
        logo = OffsetImage(plt.imread(LOGO_PATH), zoom=0.16)
        fig.add_artist(AnnotationBbox(logo, (SAFE_RIGHT - 0.08, SAFE_TOP - 0.025),
                                      xycoords='figure fraction', frameon=False, zorder=10))
    except FileNotFoundError:
        pass

    fig.text(SAFE_LEFT, SAFE_TOP - 0.035, "BEARING FAILURE", color=WHITE, fontsize=27, fontweight='bold')
    fig.text(SAFE_LEFT, SAFE_TOP - 0.068, "Real NASA sensor data  —  7 days to breakdown", color=TEXT, fontsize=13)
    if warn_t is not None:
        fig.text(SAFE_LEFT, SAFE_TOP - 0.105, f"Engine warned {hours(warn_t):.0f} hours before failure",
                 color=SCORE_C, fontsize=17, fontweight='bold')
    fig.text(SAFE_LEFT, SAFE_TOP - 0.132, f"{WINDOW}-point sliding window · k={K} · NASA IMS test 2, bearing 1",
             color=DIM, fontsize=11)
    fig.text(SAFE_LEFT, SAFE_BOTTOM - 0.025, "predictability-api.com", color=DIM, fontsize=12, fontweight='bold')

    plt.savefig("bearing_failure_short.png", dpi=DPI, facecolor=BG)
    print("Saved bearing_failure_short.png (1080x1920, Shorts-ready)")
    print(f"{len(vib)} points, {ts[0]} -> failure {end}")
    if warn_t is not None:
        print(f"Engine warning (score < {WARN}): {warn_t}  ({hours(warn_t):.1f} h early)")
    if double_t is not None:
        print(f"Vibration doubled:            {double_t}  ({hours(double_t):.1f} h early)")
    print(f"Score: {sw_s[0]:.0f} at start -> {sw_s[-1]:.0f} at failure")
    print("\n--- Vibration series (copy for a chart) ---")
    print(", ".join(f"{v:.4f}" for v in vib))


if __name__ == "__main__":
    main()
