"""umpire_fsr_charts.py
-----------------------
Umpire Consistency FSR scoring system.

Measures how consistently accurate MLB umpires call balls and strikes
using Statcast pitch location data compared to the actual call made.

Score Methodology:
  • Pull all called pitches (no swings) from Statcast
  • A pitch is "in zone" if plate_x is within ±0.83 ft AND plate_z is
    between sz_bot and sz_top (personalized per batter)
  • Correct call = in-zone called_strike OR out-of-zone ball
  • Per-game correct call % → run through FSR (k=0.5)
  • Higher FSR = more CONSISTENT accuracy game to game

Charts:
  1. Leaderboard  — all umpires ranked by FSR, top 15 vs bottom 15
  2. Umpire Card  — single umpire game-by-game accuracy trend + FSR

Usage:
    python umpire_fsr_charts.py --leaderboard
    python umpire_fsr_charts.py --leaderboard --days 30
    python umpire_fsr_charts.py --umpire "Angel Hernandez"
    python umpire_fsr_charts.py --umpire "Angel Hernandez" --game "MIN @ BAL · 1:35 PM ET"
    python umpire_fsr_charts.py --date 2026-03-29
"""
from __future__ import annotations

import argparse
import logging
import os
from datetime import date, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

try:
    from pybaseball import statcast
    _PYB_OK = True
except ImportError:
    _PYB_OK = False

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

# ── Palette (matches rest of FSR suite) ───────────────────────────────────────
BG       = "#0f1117"
PANEL    = "#171b24"
GRID     = "#2b3442"
TEXT     = "#f5f7fa"
SUB      = "#aab6c4"
ACCENT   = "#39c2ff"
GOLD     = "#ffd166"
ELITE    = "#00ff88"
VOLATILE = "#ffaa00"
DANGER   = "#ff4d4d"

# Default season window (last full season for meaningful FSR history)
SEASON_START = "2025-03-01"
SEASON_END   = "2025-11-30"

# Strike zone horizontal boundary in feet (±0.83 ≈ plate half-width + ball radius)
ZONE_X = 0.83

# ── Output directory ──────────────────────────────────────────────────────────
OUTPUT_DIR = os.path.join("static", "images", "mlb_preview", "umpires")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
#  DATA LAYER
# ─────────────────────────────────────────────────────────────────────────────

_CACHE: dict[str, pd.DataFrame] = {}


def _load_statcast(start: str, end: str) -> pd.DataFrame:
    """Pull Statcast data for a date range, with simple in-memory cache."""
    key = f"{start}|{end}"
    if key in _CACHE:
        return _CACHE[key]

    if not _PYB_OK:
        logging.error("pybaseball not installed. pip install pybaseball")
        return pd.DataFrame()

    logging.info(f"  Fetching Statcast {start} → {end} (this may take a moment)...")
    try:
        df = statcast(start, end)
    except Exception as e:
        logging.error(f"Statcast fetch failed: {e}")
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    df["game_date"] = pd.to_datetime(df["game_date"])
    _CACHE[key] = df
    return df


def _called_pitches(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to only ball/strike calls — excludes swings, HBP, bunts, etc."""
    return df[df["description"].isin(["called_strike", "ball"])].copy()


def _in_zone(df: pd.DataFrame) -> pd.Series:
    """Boolean Series: True if pitch was inside the strike zone."""
    hz = df["plate_x"].abs() <= ZONE_X
    vt = (df["plate_z"] >= df["sz_bot"]) & (df["plate_z"] <= df["sz_top"])
    return hz & vt


def _correct_call(df: pd.DataFrame) -> pd.Series:
    """Boolean Series: True if the umpire made the correct call."""
    in_zone  = _in_zone(df)
    called_k = df["description"] == "called_strike"
    called_b = df["description"] == "ball"
    return (in_zone & called_k) | (~in_zone & called_b)


def _per_game_accuracy(df: pd.DataFrame) -> pd.Series:
    """Return a Series of per-game correct call % (0–100), indexed by game_date."""
    called = _called_pitches(df)
    # Drop rows missing location data
    called = called.dropna(subset=["plate_x", "plate_z", "sz_top", "sz_bot"])
    if called.empty:
        return pd.Series(dtype=float)
    called["_correct"] = _correct_call(called)
    by_game = called.groupby("game_date")["_correct"].agg(["sum", "count"])
    by_game = by_game[by_game["count"] >= 30]   # min 30 called pitches = valid game
    accuracy = (by_game["sum"] / by_game["count"] * 100).round(2)
    return accuracy.sort_index()


def fetch_umpire_series(
    umpire_name: str,
    start: str = SEASON_START,
    end: str   = SEASON_END,
    num_games: int = 40,
) -> list[float]:
    """Return per-game called-pitch accuracy % for one umpire."""
    df = _load_statcast(start, end)
    if df.empty:
        return []

    # Statcast umpire field is typically "Last, First" — try both orderings
    mask = df["umpire"].str.lower().str.contains(
        umpire_name.lower().split()[-1], na=False
    )
    ump_df = df[mask]

    if ump_df.empty:
        logging.warning(f"No data found for umpire matching '{umpire_name}'")
        return []

    accuracy = _per_game_accuracy(ump_df)
    return accuracy.tail(num_games).tolist()


def fetch_all_umpires(
    start: str = SEASON_START,
    end: str   = SEASON_END,
    min_games: int = 10,
) -> dict[str, dict]:
    """
    Return dict keyed by umpire name:
        { 'fsr': float, 'avg_accuracy': float, 'games': int, 'series': list }
    Filters out umpires with fewer than min_games appearances.
    """
    df = _load_statcast(start, end)
    if df.empty:
        return {}

    called = _called_pitches(df)
    called = called.dropna(subset=["plate_x", "plate_z", "sz_top", "sz_bot", "umpire"])
    if called.empty:
        return {}

    called["_correct"] = _correct_call(called)
    results: dict[str, dict] = {}

    for ump_name, group in called.groupby("umpire"):
        by_game = group.groupby("game_date")["_correct"].agg(["sum", "count"])
        by_game = by_game[by_game["count"] >= 30]
        if len(by_game) < min_games:
            continue
        accuracy_series = (by_game["sum"] / by_game["count"] * 100).round(2)
        vals = accuracy_series.tolist()
        fsr  = calculate_predictability(vals, k=0.5)
        results[ump_name] = {
            "fsr":          round(fsr, 1),
            "avg_accuracy": round(float(np.mean(vals)), 1),
            "games":        len(vals),
            "series":       vals,
        }
        logging.info(f"  {ump_name:<25}  FSR {fsr:5.1f}  Acc {np.mean(vals):.1f}%  ({len(vals)} games)")

    return results


# ─────────────────────────────────────────────────────────────────────────────
#  DRAWING HELPERS
# ─────────────────────────────────────────────────────────────────────────────

_WATERMARK_IMG = None


def _stamp_watermark(fig, alpha: float = 0.30, size: float = 0.07) -> None:
    global _WATERMARK_IMG
    wm_path = os.path.join("static", "images", "watermark_yt_white.png")
    if not os.path.exists(wm_path):
        return
    if _WATERMARK_IMG is None:
        try:
            import matplotlib.image as mpimg
            _WATERMARK_IMG = mpimg.imread(wm_path)
        except Exception:
            return
    fig_w, fig_h = fig.get_size_inches()
    aspect = _WATERMARK_IMG.shape[0] / _WATERMARK_IMG.shape[1]
    w = size
    h = w * aspect * (fig_w / fig_h)
    margin = 0.01
    ax_wm = fig.add_axes([1 - w - margin, margin, w, h])
    ax_wm.imshow(_WATERMARK_IMG, alpha=alpha)
    ax_wm.axis("off")


def _fsr_color(score: float) -> str:
    if score >= 80: return ELITE
    if score >= 60: return ACCENT
    if score >= 40: return VOLATILE
    return DANGER


def _draw_umpire_panel(
    ax,
    umpire_name: str,
    values: list[float],
    game_label: str = "",
) -> None:
    """Single umpire accuracy panel — mirrors batter_fsr_charts style."""
    if not values:
        ax.set_facecolor(PANEL)
        ax.text(0.5, 0.5, f"No data\n{umpire_name}", transform=ax.transAxes,
                ha="center", va="center", color=SUB, fontsize=9)
        ax.set_title(umpire_name, color=TEXT, fontsize=8)
        return

    fsr  = calculate_predictability(values, k=0.5)
    n    = len(values)
    x    = list(range(1, n + 1))
    avg  = sum(values) / n

    ax.set_facecolor(PANEL)
    ax.spines[:].set_color(GRID)
    ax.tick_params(colors=SUB, labelsize=7)

    # 90% correct call reference line
    ax.axhline(90, color=GOLD, linewidth=1.0, linestyle="--", alpha=0.7, zorder=2)
    ax.text(0.02, 90.4, "90% ref", color=GOLD, fontsize=6, alpha=0.85,
            transform=ax.get_xaxis_transform())

    # avg line
    ax.axhline(avg, color=ACCENT, linewidth=0.7, linestyle=":", alpha=0.5, zorder=2)

    # bars colored by accuracy tier
    bar_colors = []
    for v in values:
        if v >= 92:   bar_colors.append(ELITE)
        elif v >= 88: bar_colors.append(ACCENT)
        elif v >= 84: bar_colors.append(VOLATILE)
        else:         bar_colors.append(DANGER)

    ax.bar(x, values, color=bar_colors, alpha=0.55, width=0.75, zorder=3)
    ax.plot(x, values, color=ACCENT, linewidth=1.2, zorder=4)
    ax.scatter(x[-1:], values[-1:], color=ACCENT, s=30, zorder=6)

    # sliding FSR window twin axis
    try:
        win_size = max(5, min(10, n // 4))
        win_scores, _ = calculate_sliding_window(values, window_size=win_size)
        win_x = list(range(len(win_scores)))
        ax2 = ax.twinx()
        ax2.set_facecolor("none")
        ax2.spines[:].set_color(GRID)
        ax2.tick_params(colors=SUB, labelsize=6)
        ax2.set_ylim(0, 120)
        ax2.plot(win_x, win_scores, color=GOLD, linewidth=1.0,
                 linestyle=":", alpha=0.75, zorder=5)
        ax2.set_ylabel("FSR Win.", color=GOLD, fontsize=5.5)
    except Exception:
        pass

    # FSR badge
    fsr_col = _fsr_color(fsr)
    ax.text(0.98, 0.97, f"FSR  {fsr:.1f}", transform=ax.transAxes,
            ha="right", va="top", fontsize=9, fontweight="bold", color=fsr_col,
            bbox=dict(boxstyle="round,pad=0.3", facecolor=BG, edgecolor=fsr_col, alpha=0.9))

    # avg accuracy badge
    ax.text(0.02, 0.97, f"Avg {avg:.1f}% correct", transform=ax.transAxes,
            ha="left", va="top", fontsize=7, color=SUB,
            bbox=dict(boxstyle="round,pad=0.2", facecolor=BG, edgecolor=GRID, alpha=0.8))

    # trend badge
    last_n = values[-10:]
    hot = sum(1 for v in last_n if v > avg)
    trend = "CONSISTENT" if hot >= 7 else ("ERRATIC" if hot <= 3 else "AVG")
    trend_col = ELITE if trend == "CONSISTENT" else (DANGER if trend == "ERRATIC" else SUB)
    ax.text(0.98, 0.04, f"L10: {trend}", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=7, fontweight="bold", color=trend_col,
            bbox=dict(boxstyle="round,pad=0.2", facecolor=BG, edgecolor=trend_col, alpha=0.8))

    label = f"{game_label}  ·  " if game_label else ""
    ax.set_title(f"{label}{umpire_name}  —  Called Pitch Accuracy % per Game",
                 color=TEXT, fontsize=9, pad=4)
    ax.set_ylabel("Accuracy %", color=SUB, fontsize=7)
    ax.set_xlim(0.5, n + 0.5)
    lo = max(70, min(values) - 3)
    ax.set_ylim(bottom=lo, top=100)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))


# ─────────────────────────────────────────────────────────────────────────────
#  CHART BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def build_umpire_card(
    umpire_name: str,
    game_label: str = "",
    num_games: int  = 40,
    start: str      = SEASON_START,
    end: str        = SEASON_END,
    out_path: str   = "",
) -> str:
    """Single umpire accuracy card — game-by-game trend + FSR."""
    logging.info(f"Building umpire card: {umpire_name}")
    values = fetch_umpire_series(umpire_name, start=start, end=end, num_games=num_games)

    fig, ax = plt.subplots(1, 1, figsize=(12, 5), facecolor=BG)
    fig.patch.set_facecolor(BG)

    _draw_umpire_panel(ax, umpire_name, values, game_label=game_label)

    fig.suptitle(
        "⚾  MLB Umpire Consistency  ·  Predictability Score™",
        color=TEXT, fontsize=11, fontweight="bold", y=1.01
    )

    # Methodology footnote
    fig.text(0.5, -0.02,
             "Correct call % = (in-zone called strikes + out-of-zone balls) ÷ total called pitches  |  "
             "FSR uses k=0.5 exponential decay on per-game accuracy series  |  "
             "Source: MLB Statcast via pybaseball",
             ha="center", fontsize=6, color=SUB, style="italic")

    _stamp_watermark(fig)
    plt.tight_layout()

    if not out_path:
        slug = umpire_name.lower().replace(" ", "_").replace(",", "")
        out_path = os.path.join(OUTPUT_DIR, f"umpire_{slug}.png")

    fig.savefig(out_path, dpi=150, bbox_inches="tight",
                facecolor=BG, edgecolor="none")
    plt.close(fig)
    logging.info(f"  ✓ Saved → {out_path}")
    return out_path


def build_umpire_leaderboard(
    out_path: str  = "",
    start: str     = SEASON_START,
    end: str       = SEASON_END,
    top_n: int     = 12,
    days: int | None = None,
) -> str:
    """
    Horizontal bar leaderboard: top N most consistent + bottom N most erratic umpires,
    ranked by FSR consistency score. Bars are color-coded by tier.
    """
    if days is not None:
        end   = date.today().isoformat()
        start = (date.today() - timedelta(days=days)).isoformat()

    logging.info(f"Building umpire leaderboard  {start} → {end}")
    data = fetch_all_umpires(start=start, end=end, min_games=max(5, (days or 180) // 15))

    if not data:
        logging.error("No umpire data returned — cannot build leaderboard.")
        return ""

    # Sort by FSR descending
    ranked = sorted(data.items(), key=lambda kv: kv[1]["fsr"], reverse=True)

    # Top N + bottom N (deduplicated if list is short)
    top    = ranked[:top_n]
    bottom = ranked[-top_n:]
    seen   = {name for name, _ in top}
    bottom = [(n, v) for n, v in bottom if n not in seen]

    # Build combined list: top first, then bottom (worst last)
    combined = top + bottom
    names    = [n for n, _ in combined]
    fsrs     = [v["fsr"] for _, v in combined]
    accs     = [v["avg_accuracy"] for _, v in combined]
    games    = [v["games"] for _, v in combined]
    colors   = [_fsr_color(f) for f in fsrs]

    n_total = len(combined)
    fig_h   = max(8, n_total * 0.55 + 2)
    fig, ax = plt.subplots(figsize=(13, fig_h), facecolor=BG)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(PANEL)
    ax.spines[:].set_color(GRID)
    ax.tick_params(colors=SUB, labelsize=8)

    y_pos  = list(range(n_total - 1, -1, -1))   # top of chart = highest FSR
    bars   = ax.barh(y_pos, fsrs, color=colors, alpha=0.7, height=0.6, zorder=3)

    # Grid lines
    for xg in [20, 40, 60, 80, 100]:
        ax.axvline(xg, color=GRID, linewidth=0.6, linestyle="--", alpha=0.5)

    # Labels inside/beside bars
    for i, (yp, name, fsr_val, acc, gm) in enumerate(
        zip(y_pos, names, fsrs, accs, games)
    ):
        rank   = i + 1
        col    = _fsr_color(fsr_val)
        # Umpire name (left of bar)
        ax.text(-0.5, yp, f"#{rank}  {name}", va="center", ha="right",
                color=TEXT, fontsize=7.5, fontweight="bold")
        # FSR score (inside bar)
        ax.text(fsr_val - 1.5, yp, f"{fsr_val:.1f}", va="center", ha="right",
                color=BG, fontsize=8, fontweight="bold")
        # Accuracy & games (right of bar)
        ax.text(fsr_val + 0.8, yp, f"{acc:.1f}% acc  ·  {gm}g",
                va="center", ha="left", color=SUB, fontsize=6.5)

    # Divider between top and bottom sections
    if bottom:
        divider_y = len(bottom) - 0.5
        ax.axhline(divider_y, color=GOLD, linewidth=1.0, linestyle="--", alpha=0.6)
        ax.text(50, divider_y + 0.15, "▲ Most Consistent  /  Most Erratic ▼",
                ha="center", color=GOLD, fontsize=7, alpha=0.85)

    ax.set_yticks([])
    ax.set_xlim(0, 108)
    ax.set_xlabel("FSR Consistency Score  (higher = more consistent game-to-game)",
                  color=SUB, fontsize=8)

    # Legend tiers
    for score, label in [(90, "Elite ≥80"), (70, "Good ≥60"), (50, "Volatile ≥40"), (25, "Erratic <40")]:
        col = _fsr_color(score)
        ax.text(score, -1.2, label, ha="center", fontsize=6.5, color=col, fontweight="bold")

    window_label = f"Last {days} days" if days else "2025 Season"
    fig.suptitle(
        f"⚾  MLB Umpire Consistency Leaderboard  ·  Predictability Score™  ·  {window_label}",
        color=TEXT, fontsize=13, fontweight="bold", y=1.01
    )
    fig.text(0.5, -0.01,
             "FSR = consistency of called pitch accuracy % across games  ·  "
             "Correct call: in-zone → called strike, out-of-zone → ball  ·  "
             "Min 30 called pitches/game  ·  Source: MLB Statcast via pybaseball",
             ha="center", fontsize=6, color=SUB, style="italic")

    _stamp_watermark(fig)
    plt.tight_layout()

    if not out_path:
        tag = f"last{days}d" if days else "season2025"
        out_path = os.path.join(OUTPUT_DIR, f"umpire_leaderboard_{tag}.png")

    fig.savefig(out_path, dpi=150, bbox_inches="tight",
                facecolor=BG, edgecolor="none")
    plt.close(fig)
    logging.info(f"  ✓ Saved → {out_path}")
    return out_path


def build_daily_umpire_cards(
    games: list[dict],
    date_str: str,
    num_games: int  = 40,
    start: str      = SEASON_START,
    end: str        = SEASON_END,
) -> list[str]:
    """
    Build one umpire card per game in a daily schedule dict list.
    Each game dict needs: { 'umpire': str, 'away': str, 'home': str,
                            'park': str, 'time_et': str }
    Saves to static/images/mlb_preview/2026/MM-DD/
    """
    mm_dd   = date_str[5:].replace("-", "-")
    year    = date_str[:4]
    out_dir = os.path.join("static", "images", "mlb_preview", year, mm_dd)
    os.makedirs(out_dir, exist_ok=True)

    saved = []
    for g in games:
        ump  = g.get("umpire", "").strip()
        if not ump:
            continue
        label = (f"{g.get('away','')} @ {g.get('home','')}  ·  "
                 f"{g.get('park','')}  ·  {g.get('time_et','')}")
        slug  = ump.lower().replace(" ", "_").replace(",", "")
        path  = os.path.join(out_dir, f"umpire_{slug}.png")
        build_umpire_card(ump, game_label=label, num_games=num_games,
                          start=start, end=end, out_path=path)
        saved.append(path)
    return saved


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Umpire Consistency FSR Charts")

    parser.add_argument("--leaderboard", action="store_true",
                        help="Build full umpire leaderboard chart")
    parser.add_argument("--days", type=int, default=None,
                        help="Leaderboard window in days (default: full 2025 season)")
    parser.add_argument("--top", type=int, default=12,
                        help="Number of top/bottom umpires to show (default: 12)")

    parser.add_argument("--umpire", type=str, default=None,
                        help="Build single umpire card, e.g. 'Angel Hernandez'")
    parser.add_argument("--game", type=str, default="",
                        help="Game label for the umpire card, e.g. 'MIN @ BAL · 1:35 PM ET'")
    parser.add_argument("--num-games", type=int, default=40,
                        help="Games of history to show on umpire card (default: 40)")

    parser.add_argument("--start", type=str, default=SEASON_START,
                        help=f"Start date (default: {SEASON_START})")
    parser.add_argument("--end", type=str, default=SEASON_END,
                        help=f"End date (default: {SEASON_END})")

    parser.add_argument("--out", type=str, default="",
                        help="Override output path")

    args = parser.parse_args()

    if args.leaderboard:
        build_umpire_leaderboard(
            out_path=args.out,
            start=args.start,
            end=args.end,
            top_n=args.top,
            days=args.days,
        )

    elif args.umpire:
        build_umpire_card(
            umpire_name=args.umpire,
            game_label=args.game,
            num_games=args.num_games,
            start=args.start,
            end=args.end,
            out_path=args.out,
        )

    else:
        parser.print_help()
