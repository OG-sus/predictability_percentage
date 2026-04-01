"""mlb_326_2026_graphs.py
-----------------------
Generates MLB Opening Day 2026 (March 26, 2026) preview charts for all 11 games.

For each game:
  • Pitcher FSR matchup chart -- K-rate consistency + sliding FSR window
  • Park HR context chart -- home vs. away park HR factors (3-year FSR)
  • City VPD weather chart -- outdoor stadiums only

Output root: static/images/mlb_preview/2026/03-26/

Run:
    python mlb_326_2026_graphs.py
    python mlb_326_2026_graphs.py --game-date 2026-03-26
"""
from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

try:
    from pybaseball import playerid_lookup, statcast_pitcher

    _PYBASEBALL_OK = True
except Exception:
    _PYBASEBALL_OK = False

try:
    from weather_compare import fetch_hourly_vpd

    _WEATHER_OK = True
except Exception:
    _WEATHER_OK = False

logging.basicConfig(level=logging.INFO)

# ── Output directory ──────────────────────────────────────────────────────────
GAME_DATE_STR = "2026-03-26"
OUTPUT_DIR = os.path.join("static", "images", "mlb_preview", "2026", "03-26")

# Use last completed season for meaningful FSR history
SEASON_START = "2025-03-01"
SEASON_END = "2025-11-30"

SPORTS_K = 0.5
WEATHER_K = 1.0

# ── Palette ──────────────────────────────────────────────────────────────────
BG = "#0f1117"
PANEL = "#171b24"
GRID = "#2b3442"
TEXT = "#f5f7fa"
SUB = "#aab6c4"
ACCENT = "#39c2ff"
GOLD = "#ffd166"
ELITE = "#00ff88"
VOLATILE = "#ffaa00"

# ── Team colors (primary, secondary) ─────────────────────────────────────────
TEAM_COLORS: dict[str, tuple[str, str]] = {
    "PIT": ("#FDB827", "#27251F"),
    "NYM": ("#FF5910", "#002D72"),
    "CWS": ("#C4CED4", "#27251F"),
    "MIL": ("#FFC52F", "#12284B"),
    "WSH": ("#AB0003", "#14225A"),
    "CHC": ("#CC3433", "#0E3386"),
    "MIN": ("#D31145", "#002B5C"),
    "BAL": ("#DF4601", "#1B1B1B"),
    "BOS": ("#BD3039", "#0C2340"),
    "CIN": ("#C6011F", "#1B1B1B"),
    "LAA": ("#BA0021", "#003263"),
    "HOU": ("#EB6E1F", "#002D62"),
    "DET": ("#FA4616", "#0C2340"),
    "SD":  ("#FFC425", "#2F241D"),
    "TB":  ("#8FBCE6", "#092C5C"),
    "STL": ("#C41E3A", "#0C2340"),
    "TEX": ("#C0111F", "#003278"),
    "PHI": ("#E81828", "#002D72"),
    "ARI": ("#A71930", "#E3D4AD"),
    "LAD": ("#005A9C", "#EF3E42"),
    "CLE": ("#E31937", "#0C2340"),
    "SEA": ("#005C5C", "#0C2C56"),
    "SF":  ("#FF8C42", "#27251F"),
    "NYY": ("#8FB3FF", "#1C2841"),
    "OAK": ("#EFB21E", "#003831"),
    "TOR": ("#134A8E", "#E8291C"),
    "COL": ("#333366", "#C4CED4"),
    "MIA": ("#00A3E0", "#EF3340"),
    "KC":  ("#004687", "#BD9B60"),
    "ATL": ("#CE1141", "#13274F"),
}

# ── 2026-03-26 game schedule ──────────────────────────────────────────────────
# is_dome = True  → retractable roof or fixed dome → skip VPD weather chart
GAMES: list[dict] = [
    {
        "away": "PIT", "home": "NYM",
        "away_pitcher": "Paul Skenes",        "home_pitcher": "Freddy Peralta",
        "park": "Citi Field",                  "city": "New York",
        "is_dome": False,                      "time_et": "1:15 PM",
        "tv": "NBC",
    },
    {
        "away": "CWS", "home": "MIL",
        "away_pitcher": "Shane Smith",         "home_pitcher": "Jacob Misiorowski",
        "park": "American Family Field",       "city": "Milwaukee",
        "is_dome": True,                       "time_et": "2:10 PM",
    },
    {
        "away": "WSH", "home": "CHC",
        "away_pitcher": "Cade Cavalli",        "home_pitcher": "Matthew Boyd",
        "park": "Wrigley Field",               "city": "Chicago",
        "is_dome": False,                      "time_et": "2:20 PM",
    },
    {
        "away": "MIN", "home": "BAL",
        "away_pitcher": "Joe Ryan",            "home_pitcher": "Trevor Rogers",
        "park": "Oriole Park at Camden Yards", "city": "Baltimore",
        "is_dome": False,                      "time_et": "3:05 PM",
    },
    {
        "away": "BOS", "home": "CIN",
        "away_pitcher": "Garrett Crochet",     "home_pitcher": "Andrew Abbott",
        "park": "Great American Ball Park",    "city": "Cincinnati",
        "is_dome": False,                      "time_et": "4:10 PM",
    },
    {
        "away": "LAA", "home": "HOU",
        "away_pitcher": "Jose Soriano",        "home_pitcher": "Hunter Brown",
        "park": "Daikin Park",                 "city": "Houston",
        "is_dome": True,                       "time_et": "4:10 PM",
    },
    {
        "away": "DET", "home": "SD",
        "away_pitcher": "Tarik Skubal",        "home_pitcher": "Nick Pivetta",
        "park": "Petco Park",                  "city": "San Diego",
        "is_dome": False,                      "time_et": "4:10 PM",
    },
    {
        "away": "TB",  "home": "STL",
        "away_pitcher": "Drew Rasmussen",      "home_pitcher": "Matthew Liberatore",
        "park": "Busch Stadium",               "city": "St. Louis",
        "is_dome": False,                      "time_et": "4:15 PM",
    },
    {
        "away": "TEX", "home": "PHI",
        "away_pitcher": "Nathan Eovaldi",      "home_pitcher": "Cristopher Sánchez",
        "park": "Citizens Bank Park",          "city": "Philadelphia",
        "is_dome": False,                      "time_et": "4:15 PM",
    },
    {
        "away": "ARI", "home": "LAD",
        "away_pitcher": "Zac Gallen",          "home_pitcher": "Yoshinobu Yamamoto",
        "park": "Dodger Stadium",              "city": "Los Angeles",
        "is_dome": False,                      "time_et": "8:30 PM",
        "tv": "NBC",
    },
    {
        "away": "CLE", "home": "SEA",
        "away_pitcher": "Tanner Bibee",        "home_pitcher": "Logan Gilbert",
        "park": "T-Mobile Park",               "city": "Seattle",
        "is_dome": True,                       "time_et": "10:10 PM",
    },
]

# ── Team → home park mapping ──────────────────────────────────────────────────
TEAM_PARKS: dict[str, str] = {
    "PIT": "PNC Park",
    "NYM": "Citi Field",
    "CWS": "Rate Field",
    "MIL": "American Family Field",
    "WSH": "Nationals Park",
    "CHC": "Wrigley Field",
    "MIN": "Target Field",
    "BAL": "Oriole Park at Camden Yards",
    "BOS": "Fenway Park",
    "CIN": "Great American Ball Park",
    "LAA": "Angel Stadium",
    "HOU": "Daikin Park",
    "DET": "Comerica Park",
    "SD":  "Petco Park",
    "TB":  "George M. Steinbrenner Field",
    "STL": "Busch Stadium",
    "TEX": "Globe Life Field",
    "PHI": "Citizens Bank Park",
    "ARI": "Chase Field",
    "LAD": "Dodger Stadium",
    "CLE": "Progressive Field",
    "SEA": "T-Mobile Park",
    "SF":  "Oracle Park",
    "NYY": "Yankee Stadium",
    "OAK": "Oakland Coliseum",
    "ATH": "Oakland Coliseum",  # Athletics (temp Sacramento); use OAK factors as proxy
    "TOR": "Rogers Centre",
    "COL": "Coors Field",
    "MIA": "loanDepot park",
    "KC":  "Kauffman Stadium",
    "ATL": "Truist Park",
}

# ── Park HR factor history: [2023, 2024, 2025] (% vs league avg) ──────────────
# Positive = hitter-friendly, negative = pitcher-friendly
PARK_HR_HISTORY: dict[str, list[int]] = {
    "Citi Field":                    [9, 8, 7],
    "American Family Field":         [12, 15, 14],
    "Wrigley Field":                 [4, 2, 3],
    "Oriole Park at Camden Yards":   [9, 12, 11],
    "Great American Ball Park":      [25, 28, 27],
    "Daikin Park":                   [8, 11, 10],
    "Petco Park":                    [3, 1, 2],
    "Busch Stadium":                 [-12, -15, -14],
    "Citizens Bank Park":            [16, 19, 18],
    "Dodger Stadium":                [10, 11, 12],
    "T-Mobile Park":                 [0, -2, -1],
    "PNC Park":                      [-16, -18, -17],
    "Rate Field":                    [22, 26, 24],
    "Nationals Park":                [0, -2, -1],
    "Target Field":                  [-5, -7, -6],
    "Fenway Park":                   [-18, -14, -16],
    "Angel Stadium":                 [1, 3, 2],
    "Comerica Park":                 [-3, -5, -4],
    "George M. Steinbrenner Field":  [-3, -5, -4],
    "Globe Life Field":              [5, 7, 6],
    "Chase Field":                   [-1, -3, -2],
    "Progressive Field":             [-3, -5, -4],
    "Oracle Park":                   [-22, -25, -24],
    "Yankee Stadium":                [18, 20, 19],
    "Kauffman Stadium":              [-16, -18, -17],
    "Rogers Centre":                 [9, 11, 10],
    "Truist Park":                   [-3, -5, -4],
    "Coors Field":                   [4, 8, 6],
    "loanDepot park":                [-14, -16, -15],
    "Oakland Coliseum":              [-8, -10, -9],
}


# ── Dataclass ─────────────────────────────────────────────────────────────────
@dataclass
class PitcherSeries:
    name: str
    dates: list[str]
    strikeouts: list[float]
    velocities: list[float]
    gb_rates: list[float]   # Ground-ball % per start (0-100)
    color: str


# ── Shared helpers ─────────────────────────────────────────────────────────────
def _ensure_output_dir() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _style_axes(ax: plt.Axes) -> None:
    ax.set_facecolor(PANEL)
    ax.grid(True, alpha=0.12, color=GRID)
    ax.tick_params(colors=SUB)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)


def _finish(fig: plt.Figure, path: str) -> str:
    fig.patch.set_facecolor(BG)
    plt.tight_layout()
    _stamp_watermark(fig)
    fig.savefig(path, facecolor=BG, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


_WATERMARK_IMG = None

def _stamp_watermark(fig: plt.Figure, alpha: float = 0.30, size: float = 0.07) -> None:
    """Stamp the white P% logo in the bottom-right corner of any figure."""
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
    w = size                        # fraction of figure width
    h = w * aspect * (fig_w / fig_h)
    margin = 0.01
    ax_wm = fig.add_axes([1 - w - margin, margin, w, h])
    ax_wm.imshow(_WATERMARK_IMG, alpha=alpha)
    ax_wm.axis("off")


def _fsr_badge(ax: plt.Axes, score: float, color: str, x: float = 0.98, y: float = 0.93) -> None:
    ax.text(
        x, y,
        f"FSR {score:.1f}",
        transform=ax.transAxes, ha="right", va="top",
        color=TEXT, fontsize=15, fontweight="bold",
        bbox={"boxstyle": "round,pad=0.35", "facecolor": color, "edgecolor": "none", "alpha": 0.95},
    )


def _game_slug(game: dict) -> str:
    return f"{game['away'].lower()}_{game['home'].lower()}"


# Manual overrides for pitchers whose names contain accents or are otherwise
# not resolved correctly by pybaseball's playerid_lookup.
_PITCHER_ID_OVERRIDES: dict[str, int] = {
    "jose suarez":         660761,  # stored as "josé" in pybaseball
    "jose soriano":        667755,  # stored as "josé" in pybaseball
    "shohei ohtani":       660271,
    "german marquez":      608566,  # stored as "germán márquez"
    "cristopher sanchez":  663556,  # stored as "cristópher sánchez"
    "sandy alcantara":     645261,  # stored as "sandy alcántara"
    "matthew boyd":        571510,  # stored as "matt boyd" in pybaseball
}


def _lookup_mlbam_id(player_name: str) -> int:
    key = player_name.strip().lower()
    if key in _PITCHER_ID_OVERRIDES:
        return _PITCHER_ID_OVERRIDES[key]
    parts = player_name.strip().split()
    if len(parts) < 2:
        raise ValueError(f"Need first and last name: {player_name}")
    lookup = playerid_lookup(parts[-1], parts[0])
    if lookup.empty:
        raise ValueError(f"MLBAM ID not found for {player_name}")
    return int(lookup.sort_values("mlb_played_last", ascending=False).iloc[0]["key_mlbam"])


def fetch_pitcher_series(player_name: str, num_starts: int = 12, color: str = ACCENT) -> PitcherSeries:
    if not _PYBASEBALL_OK:
        raise RuntimeError("pybaseball not available")
    mlbam_id = _lookup_mlbam_id(player_name)
    raw = statcast_pitcher(SEASON_START, SEASON_END, player_id=mlbam_id)
    if raw is None or raw.empty:
        raise ValueError(f"No Statcast data for {player_name}")

    frame = raw.copy()
    frame["game_date"] = pd.to_datetime(frame["game_date"])

    ks = (
        frame[frame["events"] == "strikeout"]
        .groupby("game_date").size().rename("ks")
    )
    velo = (
        frame[frame["release_speed"].notna()]
        .groupby("game_date")["release_speed"].mean().round(1).rename("velo")
    )

    # Ground-ball % per start from bb_type column
    bip = frame[frame["bb_type"].notna()]
    gb_count = (
        bip[bip["bb_type"] == "ground_ball"]
        .groupby("game_date").size().rename("gb")
    )
    total_bip = bip.groupby("game_date").size().rename("total_bip")
    gb_pct = (gb_count / total_bip * 100).round(1).rename("gb_pct")

    merged = pd.concat([ks, velo, gb_pct], axis=1).fillna({"ks": 0, "gb_pct": 0})
    merged = merged.dropna(subset=["velo"]).sort_index().tail(num_starts)
    if merged.empty:
        raise ValueError(f"Insufficient per-start data for {player_name}")

    return PitcherSeries(
        name=player_name,
        dates=[s.strftime("%m/%d") for s in merged.index],
        strikeouts=merged["ks"].astype(float).tolist(),
        velocities=merged["velo"].astype(float).tolist(),
        gb_rates=merged["gb_pct"].astype(float).tolist(),
        color=color,
    )


# ── Chart 1: Pitcher FSR Matchup ──────────────────────────────────────────────
def _plot_pitcher_panel(
    ax_series: plt.Axes,
    ax_fsr: plt.Axes,
    series: PitcherSeries,
    values: Optional[list[float]] = None,
    series_label: str = "Strikeouts per start",
    ylabel: str = "Strikeouts",
    avg_fmt: str = "{:.1f} K/start",
    show_velo_note: bool = True,
) -> float:
    """Plot one pitcher's metric series (top) + FSR sliding window (bottom). Returns FSR score."""
    vals = values if values is not None else series.strikeouts
    labels = series.dates
    avg = sum(vals) / len(vals)
    overall = calculate_predictability(vals, k=SPORTS_K)
    win = min(5, len(vals))
    windows = calculate_sliding_window(vals, window_size=win, k=SPORTS_K)
    scores: list[Optional[float]] = [None] * (win - 1) + [r["score"] for r in windows]

    # ── Top: raw series ───────────────────────────────────────────────────────
    _style_axes(ax_series)
    ax_series.plot(labels, vals, marker="o", markersize=5, linewidth=2.6,
                   color=series.color, alpha=0.95, zorder=3)
    ax_series.axhline(avg, color=GOLD, linestyle="--", linewidth=1.4,
                      label=f"Season avg  {avg_fmt.format(avg)}")
    ax_series.fill_between(labels, vals, alpha=0.08, color=series.color)
    ax_series.set_title(series_label, color=TEXT, fontsize=12, pad=8)
    ax_series.set_ylabel(ylabel, color=TEXT)
    # Whole-number ticks for counting stats (K, GB%) — not for float metrics
    if not any(c in ylabel.lower() for c in [".", "velo", "speed", "mph"]):
        ax_series.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax_series.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, framealpha=0.6,
                     fontsize=9)
    ax_series.tick_params(axis="x", rotation=45, labelsize=8)
    ax_series.text(0.02, 0.96, series.name.upper(), transform=ax_series.transAxes,
                   ha="left", va="top", color=series.color, fontsize=14, fontweight="bold")
    _fsr_badge(ax_series, overall, series.color)

    # ── Bottom: FSR sliding window ────────────────────────────────────────────
    _style_axes(ax_fsr)
    ax_fsr.axhspan(80, 105, color="#103b2e", alpha=0.20)
    ax_fsr.axhspan(60, 80,  color="#4b3d12", alpha=0.14)
    ax_fsr.plot(labels, scores, linewidth=2.4, color=ACCENT,
                label=f"Predictability Score ({win}-start window)")
    ax_fsr.axhline(overall, color=series.color, linestyle="--", linewidth=1.2,
                   label=f"Season FSR: {overall:.1f}")
    ax_fsr.axhline(80, color=ELITE,    linestyle=":", linewidth=1.0, label="Elite  (80)")
    ax_fsr.axhline(60, color=VOLATILE, linestyle=":", linewidth=1.0, label="Volatile (60)")
    ax_fsr.set_title("FSR Predictability Score™", color=TEXT, fontsize=12, pad=8)
    ax_fsr.set_ylabel("Score (0-100)", color=TEXT)
    ax_fsr.set_xlabel("2025 start date", color=TEXT)
    ax_fsr.set_ylim(0, 108)
    ax_fsr.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, framealpha=0.6,
                  fontsize=9)
    ax_fsr.tick_params(axis="x", rotation=45, labelsize=8)

    # Optional velocity note in FSR panel
    if show_velo_note and series.velocities:
        avg_velo = sum(series.velocities) / len(series.velocities)
        ax_fsr.text(0.02, 0.94, f"Avg velo  {avg_velo:.1f} mph",
                    transform=ax_fsr.transAxes, ha="left", va="top",
                    color=SUB, fontsize=9,
                    bbox={"boxstyle": "round,pad=0.25", "facecolor": "#202634",
                          "edgecolor": GRID, "alpha": 0.90})

    return overall


def save_pitcher_matchup_chart(game: dict) -> str:
    away, home = game["away"], game["home"]
    away_p, home_p = game["away_pitcher"], game["home_pitcher"]
    away_color = TEAM_COLORS.get(away, (ACCENT, PANEL))[0]
    home_color = TEAM_COLORS.get(home, (ACCENT, PANEL))[0]

    away_series: Optional[PitcherSeries] = None
    home_series: Optional[PitcherSeries] = None

    try:
        away_series = fetch_pitcher_series(away_p, color=away_color)
        logging.info(f"  + {away_p} -- {len(away_series.strikeouts)} starts loaded")
    except Exception as exc:
        logging.warning(f"  x {away_p}: {exc}")

    try:
        home_series = fetch_pitcher_series(home_p, color=home_color)
        logging.info(f"  + {home_p} -- {len(home_series.strikeouts)} starts loaded")
    except Exception as exc:
        logging.warning(f"  x {home_p}: {exc}")

    path = os.path.join(OUTPUT_DIR, f"pitcher_{_game_slug(game)}.png")

    if away_series is None and home_series is None:
        return _save_no_data_chart(f"{away_p}  vs  {home_p}\n\nNo 2025 Statcast data available.", path)

    fig, axes = plt.subplots(2, 2, figsize=(15, 9.5))
    for ax in axes.flatten():
        _style_axes(ax)

    away_fsr = 0.0
    home_fsr = 0.0

    if away_series:
        away_fsr = _plot_pitcher_panel(axes[0][0], axes[1][0], away_series)
    else:
        _draw_unavailable(axes[0][0], away_p)
        _draw_unavailable(axes[1][0], "")

    if home_series:
        home_fsr = _plot_pitcher_panel(axes[0][1], axes[1][1], home_series)
    else:
        _draw_unavailable(axes[0][1], home_p)
        _draw_unavailable(axes[1][1], "")

    # ── FSR head-to-head header ───────────────────────────────────────────────
    matchup_line = f"{away_p}  vs  {home_p}"
    fig.suptitle(
        f"{away} @ {home}  |  {game.get('park', '')}  |  {game.get('time_et', '')}",
        color=TEXT, fontsize=17, fontweight="bold", y=1.01,
    )

    # Build FSR comparison subtitle
    if away_series and home_series:
        diff = away_fsr - home_fsr
        if abs(diff) >= 1.0:
            winner_name = away_p if diff > 0 else home_p
            winner_color = away_color if diff > 0 else home_color
            edge_text = (
                f"Strikeout Predictability:  "
                f"{away_p.split()[-1]} {away_fsr:.1f}  vs  "
                f"{home_p.split()[-1]} {home_fsr:.1f}  "
                f"|  MORE PREDICTABLE: {winner_name.split()[-1].upper()} (+{abs(diff):.1f} FSR pts)"
            )
        else:
            edge_text = (
                f"Strikeout Predictability:  "
                f"{away_p.split()[-1]} {away_fsr:.1f}  vs  "
                f"{home_p.split()[-1]} {home_fsr:.1f}  |  ESSENTIALLY EQUAL"
            )
    elif away_series:
        edge_text = f"FSR  {away_p.split()[-1]}: {away_fsr:.1f}  |  {home_p}: data unavailable"
    elif home_series:
        edge_text = f"FSR  {home_p.split()[-1]}: {home_fsr:.1f}  |  {away_p}: data unavailable"
    else:
        edge_text = matchup_line

    fig.text(0.5, 0.975, edge_text, ha="center", color=GOLD, fontsize=12, fontweight="bold")
    fig.text(
        0.5, 0.007,
        "FSR Predictability Score™ -- Raw K-rate series (top) + sliding 5-start window (bottom)."
        "  Higher FSR = more consistent, more predictable pitcher.",
        ha="center", color=SUB, fontsize=9.5,
    )

    return _finish(fig, path)


# ── Chart 1b: Pitcher GB% FSR chart ──────────────────────────────────────────
def save_pitcher_gbfb_chart(game: dict) -> str:
    """Ground-ball % consistency chart for both starters. Mirrors the K-rate chart layout."""
    away, home = game["away"], game["home"]
    away_p, home_p = game["away_pitcher"], game["home_pitcher"]
    away_color = TEAM_COLORS.get(away, (ACCENT, PANEL))[0]
    home_color = TEAM_COLORS.get(home, (ACCENT, PANEL))[0]

    away_series: Optional[PitcherSeries] = None
    home_series: Optional[PitcherSeries] = None

    try:
        away_series = fetch_pitcher_series(away_p, color=away_color)
    except Exception:
        pass
    try:
        home_series = fetch_pitcher_series(home_p, color=home_color)
    except Exception:
        pass

    path = os.path.join(OUTPUT_DIR, f"gbfb_{_game_slug(game)}.png")

    if away_series is None and home_series is None:
        return _save_no_data_chart(f"{away_p}  vs  {home_p}\n\nNo GB% data available.", path)

    fig, axes = plt.subplots(2, 2, figsize=(15, 9.5))
    for ax in axes.flatten():
        _style_axes(ax)

    away_fsr = 0.0
    home_fsr = 0.0

    gb_kwargs = dict(
        series_label="Ground-ball % per start",
        ylabel="GB%",
        avg_fmt="{:.1f}% avg GB rate",
        show_velo_note=False,
    )

    if away_series and any(v > 0 for v in away_series.gb_rates):
        away_fsr = _plot_pitcher_panel(axes[0][0], axes[1][0], away_series,
                                       values=away_series.gb_rates, **gb_kwargs)
    else:
        _draw_unavailable(axes[0][0], away_p)
        _draw_unavailable(axes[1][0], "")

    if home_series and any(v > 0 for v in home_series.gb_rates):
        home_fsr = _plot_pitcher_panel(axes[0][1], axes[1][1], home_series,
                                       values=home_series.gb_rates, **gb_kwargs)
    else:
        _draw_unavailable(axes[0][1], home_p)
        _draw_unavailable(axes[1][1], "")

    fig.suptitle(
        f"{away} @ {home}  |  {game.get('park', '')}  |  GB% CONSISTENCY",
        color=TEXT, fontsize=17, fontweight="bold", y=1.01,
    )

    if away_series and home_series and away_fsr > 0 and home_fsr > 0:
        diff = away_fsr - home_fsr
        winner = (away_p if diff > 0 else home_p).split()[-1].upper()
        sub = (
            f"Ground-ball Predictability:  "
            f"{away_p.split()[-1]} {away_fsr:.1f}  vs  {home_p.split()[-1]} {home_fsr:.1f}"
            + (f"  |  MORE CONSISTENT: {winner} (+{abs(diff):.1f})" if abs(diff) >= 1.0 else "  |  EVEN MATCH")
        )
    else:
        sub = "Ground-ball rate consistency -- 2025 season"

    fig.text(0.5, 0.975, sub, ha="center", color=GOLD, fontsize=12, fontweight="bold")
    fig.text(
        0.5, 0.007,
        "High GB% FSR = pitcher reliably induces weak contact / limits fly balls."
        "  Volatile GB% = harder to predict HR risk per start.",
        ha="center", color=SUB, fontsize=9.5,
    )

    return _finish(fig, path)


# ── Chart 2: Park HR context ──────────────────────────────────────────────────
def save_park_context_chart(game: dict, out_path_override: str | None = None) -> str:
    home, away = game["home"], game["away"]
    home_park = game.get("park") or TEAM_PARKS.get(home, "Unknown Park")
    away_park = TEAM_PARKS.get(away)

    home_history = PARK_HR_HISTORY.get(home_park, [0, 0, 0])
    away_history = PARK_HR_HISTORY.get(away_park, [0, 0, 0]) if away_park else [0, 0, 0]

    home_fsr = calculate_predictability([abs(v) for v in home_history], k=SPORTS_K) if len(home_history) >= 2 else None
    away_fsr = calculate_predictability([abs(v) for v in away_history], k=SPORTS_K) if len(away_history) >= 2 else None

    home_factor = home_history[-1]  # current-year value
    away_factor = away_history[-1]

    home_color = TEAM_COLORS.get(home, (ACCENT, PANEL))[0]
    away_color = TEAM_COLORS.get(away, (ACCENT, PANEL))[0]

    fig, (ax_bar, ax_hist) = plt.subplots(1, 2, figsize=(14, 6.5),
                                           gridspec_kw={"width_ratios": [1.6, 2]})
    _style_axes(ax_bar)
    _style_axes(ax_hist)

    # ── Left: today's two parks, side-by-side ─────────────────────────────────
    bars = [home_factor, away_factor]
    colors = [
        ("#ff6b6b" if home_factor > 0 else "#6bcb77"),
        ("#ff6b6b" if away_factor > 0 else "#6bcb77"),
    ]
    labels = [f"{home}\n{home_park}", f"{away}\n{away_park or 'Away Park'}"]
    positions = [0, 1]
    bar_objs = ax_bar.bar(positions, bars, color=colors, width=0.48, zorder=3, edgecolor=BG, linewidth=0.8)
    ax_bar.axhline(0, color="#d8dee9", linewidth=1.2, zorder=4)

    for bar_obj, val in zip(bar_objs, bars):
        vert = bar_obj.get_height() + (1.5 if val >= 0 else -3.0)
        ax_bar.text(bar_obj.get_x() + bar_obj.get_width() / 2, vert,
                    f"{val:+d}%", ha="center", color=TEXT, fontsize=13, fontweight="bold")

    ax_bar.set_xticks(positions)
    ax_bar.set_xticklabels(labels, color=SUB, fontsize=11)
    ax_bar.set_title("HR FACTOR VS LEAGUE AVG", color=TEXT, fontsize=14, pad=10, fontweight="bold")
    ax_bar.set_ylabel("HR factor (%)", color=TEXT)

    # FSR badges
    if home_fsr is not None:
        ax_bar.text(0.02, 0.97, f"FSR {home_fsr:.1f}", transform=ax_bar.transAxes,
                    ha="left", va="top", color=TEXT, fontsize=12, fontweight="bold",
                    bbox={"boxstyle": "round,pad=0.3", "facecolor": home_color, "edgecolor": "none", "alpha": 0.95})
    if away_fsr is not None:
        ax_bar.text(0.98, 0.97, f"FSR {away_fsr:.1f}", transform=ax_bar.transAxes,
                    ha="right", va="top", color=TEXT, fontsize=12, fontweight="bold",
                    bbox={"boxstyle": "round,pad=0.3", "facecolor": away_color, "edgecolor": "none", "alpha": 0.95})

    delta = home_factor - away_factor
    direction = "more hitter-friendly" if delta > 0 else "more pitcher-friendly"
    ax_bar.text(0.5, 0.05,
                f"Today's park is {abs(delta)} pts {direction}\nthan {away}'s home turf",
                transform=ax_bar.transAxes, ha="center", va="bottom",
                color=SUB, fontsize=10,
                bbox={"boxstyle": "round,pad=0.35", "facecolor": "#202634", "edgecolor": GRID, "alpha": 0.85})

    # ── Right: 3-year trend ────────────────────────────────────────────────────
    years = ["2023", "2024", "2025"]
    ax_hist.plot(years, home_history, marker="o", markersize=7, linewidth=2.6,
                 color=home_color, label=f"{home} -- {home_park}")
    ax_hist.plot(years, away_history, marker="s", markersize=7, linewidth=2.6,
                 color=away_color, linestyle="--", label=f"{away} -- {away_park or 'Away Park'}")
    ax_hist.axhline(0, color="#d8dee9", linewidth=1.0, linestyle=":")
    ax_hist.fill_between(years, home_history, alpha=0.08, color=home_color)
    ax_hist.fill_between(years, away_history, alpha=0.08, color=away_color)

    ax_hist.set_title("3-YEAR HR FACTOR TREND", color=TEXT, fontsize=14, pad=10, fontweight="bold")
    ax_hist.set_ylabel("HR factor (%)", color=TEXT)
    ax_hist.set_xlabel("Season", color=TEXT)
    ax_hist.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, framealpha=0.7)

    ax_hist.text(
        0.5, 0.96,
        "FSR on 3-yr trend = park factor consistency over time",
        transform=ax_hist.transAxes, ha="center", va="top",
        color=SUB, fontsize=9.5,
    )

    fig.suptitle(
        f"PARK HR CONTEXT  |  {home_park}  |  {away} @ {home}",
        color=TEXT, fontsize=16, fontweight="bold", y=1.01,
    )

    path = out_path_override or os.path.join(OUTPUT_DIR, f"park_{home.lower()}.png")
    return _finish(fig, path)


# ── Chart 3: City VPD weather (outdoor only) ──────────────────────────────────
def save_city_vpd_chart(game: dict, end_date: date) -> Optional[str]:
    if not _WEATHER_OK:
        logging.warning("weather_compare not available; skipping VPD chart")
        return None

    city = game["city"]
    home = game["home"]
    home_color = TEAM_COLORS.get(home, (ACCENT, PANEL))[0]
    start_date = end_date - timedelta(days=29)

    try:
        _, values = fetch_hourly_vpd(city, start_date, end_date, aggregation="daily")
    except Exception as exc:
        logging.warning(f"VPD fetch failed for {city}: {exc}")
        return None

    if not values or len(values) < 3:
        logging.warning(f"Insufficient VPD data for {city}")
        return None

    series = list(values)
    labels = [(start_date + timedelta(days=i)).strftime("%m/%d") for i in range(len(series))]
    avg = sum(series) / len(series)
    overall = calculate_predictability(series, k=WEATHER_K)
    win = min(7, len(series))
    windows = calculate_sliding_window(series, window_size=win, k=WEATHER_K)
    scores: list[Optional[float]] = [None] * (win - 1) + [r["score"] for r in windows]

    # ── Fetch "this time last year" data ─────────────────────────────────────
    prev_series: list[float] = []
    prev_avg: Optional[float] = None
    prev_start = start_date - timedelta(days=365)
    prev_end = end_date - timedelta(days=365)
    try:
        _, prev_raw = fetch_hourly_vpd(city, prev_start, prev_end, aggregation="daily")
        prev_series = list(prev_raw) if prev_raw else []
        if prev_series:
            prev_avg = sum(prev_series) / len(prev_series)
    except Exception:
        pass  # YoY overlay is optional

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12.5, 8.2))
    _style_axes(ax1)
    _style_axes(ax2)

    # ── Top: VPD series + YoY overlay ────────────────────────────────────────
    ax1.plot(labels, series, color=home_color, linewidth=2.4, marker="o", markersize=4,
             label=f"2026  (30-day avg {avg:.2f} kPa)", zorder=3)
    ax1.axhline(avg, color=GOLD, linestyle="--", linewidth=1.3, alpha=0.8)
    ax1.fill_between(labels, series, alpha=0.07, color=home_color)

    if prev_series:
        # Align to same number of days if lengths differ
        n = min(len(series), len(prev_series))
        prev_labels_aligned = labels[:n]
        prev_series_aligned = prev_series[:n]
        ax1.plot(prev_labels_aligned, prev_series_aligned,
                 color="#888ea8", linewidth=1.6, linestyle="--", marker="s",
                 markersize=2.5, alpha=0.65, label=f"2025 same window (avg {prev_avg:.2f} kPa)",
                 zorder=2)
        # YoY delta annotation
        yoy_delta = avg - prev_avg
        delta_sign = "+" if yoy_delta >= 0 else ""
        delta_color = "#ff8c42" if yoy_delta > 0.05 else ("#6bcb77" if yoy_delta < -0.05 else SUB)
        ax1.text(0.98, 0.08,
                 f"YoY avg  {delta_sign}{yoy_delta:.2f} kPa",
                 transform=ax1.transAxes, ha="right", va="bottom",
                 color=delta_color, fontsize=10, fontweight="bold",
                 bbox={"boxstyle": "round,pad=0.3", "facecolor": "#202634",
                       "edgecolor": GRID, "alpha": 0.90})

    ax1.set_title(f"{city.upper()} AIR STABILITY -- {game['park']}", color=TEXT,
                  fontsize=15, pad=10, fontweight="bold")
    ax1.set_ylabel("VPD (kPa)", color=TEXT)
    ax1.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, framealpha=0.6)
    ax1.tick_params(axis="x", rotation=45, labelsize=8)
    ax1.text(0.02, 0.96,
             "Higher VPD = hotter & drier air. Ball carries farther (lower air density).",
             transform=ax1.transAxes, ha="left", va="top", color=SUB, fontsize=9.5)
    _fsr_badge(ax1, overall, home_color)

    # ── Bottom: FSR sliding window ─────────────────────────────────────────────
    ax2.axhspan(80, 105, color="#103b2e", alpha=0.20)
    ax2.axhspan(60, 80,  color="#4b3d12", alpha=0.14)
    ax2.plot(labels, scores, linewidth=2.3, color=ACCENT,
             label=f"Predictability ({win}-day window)")
    ax2.axhline(overall, color=home_color, linestyle="--", linewidth=1.2,
                label=f"Overall FSR  {overall:.1f}")
    ax2.axhline(80, color=ELITE,    linestyle=":", linewidth=1, label="Elite (80)")
    ax2.axhline(60, color=VOLATILE, linestyle=":", linewidth=1, label="Volatile (60)")
    ax2.set_title("FSR PREDICTABILITY SCORE™", color=TEXT, fontsize=13, pad=10, fontweight="bold")
    ax2.set_ylabel("Score (0-100)", color=TEXT)
    ax2.set_xlabel("Date (2026)", color=TEXT)
    ax2.set_ylim(0, 108)
    ax2.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, framealpha=0.6)
    ax2.tick_params(axis="x", rotation=45, labelsize=8)

    city_slug = city.lower().replace(" ", "_")
    path = os.path.join(OUTPUT_DIR, f"vpd_{city_slug}.png")
    return _finish(fig, path)


# ── Fallback charts ───────────────────────────────────────────────────────────
def _draw_unavailable(ax: plt.Axes, label: str) -> None:
    _style_axes(ax)
    ax.text(0.5, 0.5, f"{label}\n\nNo 2025 Statcast data",
            transform=ax.transAxes, ha="center", va="center",
            color=SUB, fontsize=11)


def _save_no_data_chart(message: str, path: str) -> str:
    fig, ax = plt.subplots(figsize=(10, 4))
    _style_axes(ax)
    ax.text(0.5, 0.5, message, transform=ax.transAxes,
            ha="center", va="center", color=SUB, fontsize=13)
    return _finish(fig, path)


# ── Summary: FSR scores for all pitchers ─────────────────────────────────────
def save_fsr_summary_chart(results: list[dict]) -> str:
    """Horizontal bar chart showing FSR score for every starting pitcher."""
    pitcher_scores = [r for r in results if r.get("away_fsr") is not None or r.get("home_fsr") is not None]
    if not pitcher_scores:
        return ""

    names: list[str] = []
    scores: list[float] = []
    colors: list[str] = []

    for r in pitcher_scores:
        game = r["game"]
        if r.get("away_fsr") is not None:
            names.append(f"{game['away_pitcher'].split()[-1]} ({game['away']})")
            scores.append(r["away_fsr"])
            colors.append(TEAM_COLORS.get(game["away"], (ACCENT, PANEL))[0])
        if r.get("home_fsr") is not None:
            names.append(f"{game['home_pitcher'].split()[-1]} ({game['home']})")
            scores.append(r["home_fsr"])
            colors.append(TEAM_COLORS.get(game["home"], (ACCENT, PANEL))[0])

    # Sort descending by FSR
    sorted_pairs = sorted(zip(scores, names, colors), reverse=True)
    scores, names, colors = zip(*sorted_pairs) if sorted_pairs else ([], [], [])

    fig, ax = plt.subplots(figsize=(12, max(5, len(names) * 0.55 + 2)))
    _style_axes(ax)

    y_pos = list(range(len(names)))
    bars = ax.barh(y_pos, scores, color=list(colors), height=0.7, edgecolor=BG, linewidth=0.6)

    for bar_obj, score in zip(bars, scores):
        ax.text(bar_obj.get_width() + 0.5, bar_obj.get_y() + bar_obj.get_height() / 2,
                f"{score:.1f}", va="center", ha="left", color=TEXT, fontsize=9.5, fontweight="bold")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, color=SUB, fontsize=10)
    ax.axvline(80, color=ELITE,    linestyle=":", linewidth=1.2, label="Elite (80)")
    ax.axvline(60, color=VOLATILE, linestyle=":", linewidth=1.2, label="Volatile (60)")
    ax.set_xlim(0, 108)
    ax.set_xlabel("FSR Predictability Score™ (0-100)", color=TEXT)
    ax.set_title("OPENING DAY 2026  |  STARTER FSR LEADERBOARD  |  MARCH 26",
                 color=TEXT, fontsize=15, pad=12, fontweight="bold")
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, framealpha=0.7)
    ax.text(0.5, -0.09,
            "Based on 2025 season K-rate consistency (k=0.5).  Higher = more predictable across starts.",
            transform=ax.transAxes, ha="center", color=SUB, fontsize=9.5)

    path = os.path.join(OUTPUT_DIR, "summary_fsr_starters.png")
    return _finish(fig, path)


# ── Main generator ────────────────────────────────────────────────────────────
def generate_326_charts(end_date: Optional[date] = None) -> list[str]:
    _ensure_output_dir()
    # Default to the game date itself so charts always end on 3/26 regardless of local timezone
    target = end_date or date.fromisoformat(GAME_DATE_STR)
    generated: list[str] = []
    results: list[dict] = []

    logging.info(f"\n{'='*60}")
    logging.info(f"  MLB 2026-03-26 Preview Charts  |  {len(GAMES)} games")
    logging.info(f"{'='*60}\n")

    for i, game in enumerate(GAMES, 1):
        away, home = game["away"], game["home"]
        slug = _game_slug(game)
        dome_tag = "  DOME" if game.get("is_dome") else ""
        logging.info(f"[{i}/{len(GAMES)}]  {away} @ {home}  --  {game.get('time_et', '')}{dome_tag}")

        result: dict = {"game": game, "away_fsr": None, "home_fsr": None}

        # Pitcher matchup chart (K-rate)
        try:
            p = save_pitcher_matchup_chart(game)
            generated.append(p)
            logging.info(f"   + Pitcher K-rate chart → {os.path.basename(p)}")
        except Exception as exc:
            logging.error(f"   x Pitcher chart failed: {exc}")

        # Pitcher GB% consistency chart
        try:
            p = save_pitcher_gbfb_chart(game)
            generated.append(p)
            logging.info(f"   + Pitcher GB% chart   → {os.path.basename(p)}")
        except Exception as exc:
            logging.error(f"   x GB% chart failed: {exc}")

        # Park context chart
        try:
            p = save_park_context_chart(game)
            generated.append(p)
            logging.info(f"   + Park chart    → {os.path.basename(p)}")
        except Exception as exc:
            logging.error(f"   x Park chart failed: {exc}")

        # VPD weather chart (outdoor only)
        if not game.get("is_dome"):
            try:
                p = save_city_vpd_chart(game, target)
                if p:
                    generated.append(p)
                    logging.info(f"   + VPD chart     → {os.path.basename(p)}")
            except Exception as exc:
                logging.warning(f"   x VPD chart failed: {exc}")

        results.append(result)

    # Summary FSR leaderboard (only if at least some pitcher data was gathered)
    try:
        p = save_fsr_summary_chart(results)
        if p:
            generated.append(p)
            logging.info(f"\n+ Summary chart  → {os.path.basename(p)}")
    except Exception as exc:
        logging.warning(f"Summary chart failed: {exc}")

    logging.info(f"\n{'='*60}")
    logging.info(f"  Done -- {len(generated)} charts saved to {OUTPUT_DIR}")
    logging.info(f"{'='*60}\n")
    return generated


# ── CLI ───────────────────────────────────────────────────────────────────────
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate MLB 2026-03-26 preview charts.")
    parser.add_argument("--game-date", default=None,
                        help="Date in YYYY-MM-DD format (defaults to today).")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    target_date = date.fromisoformat(args.game_date) if args.game_date else None
    paths = generate_326_charts(target_date)
    print(f"\nGenerated {len(paths)} charts:")
    for path in paths:
        print(f"  {path}")
