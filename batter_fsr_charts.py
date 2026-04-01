"""batter_fsr_charts.py
-----------------------
Generates batter consistency FSR charts for MLB games.
Reusable throughout the 2026 season.

Usage:
    python batter_fsr_charts.py
    python batter_fsr_charts.py --date 2026-03-26

Outputs to: static/images/mlb_preview/2026/MM-DD/
"""
from __future__ import annotations

import argparse
import logging
import os
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

try:
    from pybaseball import statcast_batter, statcast_pitcher
    _PYB_OK = True
except ImportError:
    _PYB_OK = False

logging.basicConfig(level=logging.INFO)

# ── Palette ───────────────────────────────────────────────────────────────────
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

SEASON_START = "2025-03-01"
SEASON_END   = "2025-11-30"

# ── Known MLBAM IDs (accent/encoding-safe) ────────────────────────────────────
PLAYER_IDS: dict[str, int] = {
    # LAD
    "shohei ohtani":       660271,
    "freddie freeman":     518692,
    "mookie betts":        605141,
    "will smith":          669257,
    "max muncy":           571970,
    "teoscar hernandez":   606192,
    "tommy edman":         669242,
    # ARI
    "corbin carroll":      682998,
    "ketel marte":         606466,
    "christian walker":    572233,
    "lourdes gurriel":     666971,
    "joc pederson":        592626,
    # CLE
    "jose ramirez":        608070,
    "steven kwan":         680757,
    "brayan rocchio":      682626,
    "josh naylor":         647304,
    # SEA
    "julio rodriguez":     677594,
    "cal raleigh":         663728,
    "mitch garver":        608348,
    "jorge polanco":       553869,
    # SEA pitchers
    "luis castillo":       622379,
    "logan gilbert":       669302,
    # LAD pitchers
    "roki sasaki":         808963,
    # Closers / relievers
    "emmanuel clase":      661403,
    "andres munoz":        668678,
    "evan phillips":       656975,
    "kevin ginkel":        661563,
    "paul sewald":         534950,
    "ryan helsley":        664315,
    # KC bullpen
    "carlos estevez":      621107,
    "james mcarthur":      656685,
    "daniel lynch":        663776,
    # ATL bullpen
    "aj minter":           621313,
    "a.j. minter":         621313,
    "pierce johnson":      605195,
    "joe jimenez":         650406,
    "raisel iglesias":     596747,
    # ARI bullpen
    "miguel castro":       592699,
    "justin martinez":     682721,
    # LAD bullpen
    "brusdar graterol":    666142,
    "alex vesia":          672710,
    "michael kopech":      645261,
    # CLE bullpen
    "cade smith":          671922,
    "hunter gaddis":       683301,
    "nick sandlin":        680710,
    # SEA bullpen
    "matt brash":          680694,
    "trent thornton":      622259,
    # SD bullpen
    "robert suarez":       622766,
    "tom cosgrove":        669701,
    # NYY bullpen
    "max fried":           608331,
    "jake cousins":        664776,
    "luke weaver":         621592,
    "ian hamilton":        672779,
    # SF bullpen
    "ryan walker":         672584,
    "camilo doval":        666818,
    # DET bullpen
    "jason foley":         656678,
    "tyler holton":        683632,
    # KC Royals
    "salvador perez":      521692,
    "bobby witt":          677951,
    "bobby witt jr":       677951,
    "vinnie pasquantino":  686469,
    "michael massey":      680977,
    "hunter renfroe":      592669,
    # ATL Braves
    "ronald acuna":        665161,
    "ronald acuna jr":     665161,
    "ozzie albies":        645277,
    "austin riley":        663586,
    "michael harris":      678882,
    "marcell ozuna":       542303,
    # ATL pitchers
    "chris sale":          519242,
    "max fried":           608331,
    "spencer strider":     675911,
    # NYY
    "juan soto":           665742,
    "aaron judge":         592450,
    "giancarlo stanton":   519317,
    "anthony volpe":       694497,
    "jazz chisholm":       665750,
    # SF
    "mike yastrzemski":    641933,
    "heliot ramos":        671218,
    "patrick bailey":      683003,
    "matt chapman":        572761,
    # HOU
    "yordan alvarez":      670541,
    "alex bregman":        608324,
    "jose abreu":          547989,
    "kyle tucker":         663527,
    # DET
    "kerry carpenter":     681481,
    "riley greene":        682985,
    "spencer torkelson":   679529,
    # SD Padres
    "xander bogaerts":     572761,
    "jackson merrill":     701538,
    "jake cronenworth":    668942,
    "fernando tatis":      665487,
    # Misc stars
    "kyle schwarber":      656941,
    "eugenio suarez":      553993,
    "rafael devers":       646240,
    "vladimir guerrero":   665489,
    "bo bichette":         666182,
    "trea turner":         607208,
    "bryce harper":        547180,
    "pete alonso":         624413,
    "matt olson":          621566,
    "gunnar henderson":    683002,
    "adley rutschman":     668939,
    # TEX Rangers
    "corey seager":          608369,
    "marcus semien":         543760,
    "nathaniel lowe":        663993,
    # PHI Phillies
    "nick castellanos":      592206,
    # Pitchers used in star charts
    "jacob degrom":          594798,
    "tyler glasnow":         607192,
    "paul skenes":           694973,
    "tarik skubal":          669373,
    "garrett crochet":       676979,
    # DET closer
    "alex lange":            650895,
    # TEX bullpen
    "jose leclerc":          600917,
    "jonathan hernandez":    666201,
    "kirby yates":           605198,
    # PHI bullpen
    "seranthony dominguez":  622517,
    "jeff hoffman":          601713,
    "jose alvarado":         636860,
    # CIN
    "elly de la cruz":       682829,
    # MIN
    "royce lewis":           668686,
    "byron buxton":          621439,
    # MIN pitchers
    "simeon woods richardson": 680573,
    # MIL
    "christian yelich":      592885,
    "william contreras":     661388,
}

TEAM_COLORS: dict[str, tuple[str, str]] = {
    "LAD": ("#005A9C", "#EF3E42"),
    "ARI": ("#A71930", "#E3D4AD"),
    "CLE": ("#E31937", "#0C2340"),
    "SEA": ("#005C5C", "#0C2C56"),
    "NYY": ("#8FB3FF", "#1C2841"),
    "PHI": ("#E81828", "#002D72"),
    "BOS": ("#BD3039", "#0C2340"),
    "CIN": ("#C6011F", "#1B1B1B"),
    "PIT": ("#FDB827", "#27251F"),
    "NYM": ("#FF5910", "#002D72"),
    "BAL": ("#DF4601", "#1B1B1B"),
    "MIN": ("#D31145", "#002B5C"),
    "CHC": ("#CC3433", "#0E3386"),
    "WSH": ("#AB0003", "#14225A"),
    "MIL": ("#FFC52F", "#12284B"),
    "DET": ("#FA4616", "#0C2340"),
    "SD":  ("#FFC425", "#2F241D"),
    "STL": ("#C41E3A", "#0C2340"),
    "TB":  ("#8FBCE6", "#092C5C"),
    "TEX": ("#C0111F", "#003278"),
    "HOU": ("#EB6E1F", "#002D62"),
    "LAA": ("#BA0021", "#003263"),
    "SF":  ("#FF8C42", "#27251F"),
    "OAK": ("#EFB21E", "#003831"),
    "TOR": ("#134A8E", "#E8291C"),
    "ATL": ("#CE1141", "#13274F"),
    "MIA": ("#00A3E0", "#EF3340"),
    "KC":  ("#004687", "#BD9B60"),
    "COL": ("#33006F", "#C4CED4"),
    "CHW": ("#C4CED4", "#27251F"),
    "CWS": ("#C4CED4", "#27251F"),   # White Sox alias
    "ATH": ("#EFB21E", "#003831"),   # Athletics (green/gold)
}


# ── Data fetching ─────────────────────────────────────────────────────────────

def _tb_from_events(df: pd.DataFrame) -> pd.Series:
    tb_map = {"single": 1, "double": 2, "triple": 3, "home_run": 4}
    hits = df[df["events"].isin(tb_map)].copy()
    hits["_tb"] = hits["events"].map(tb_map)
    return hits.groupby("game_date")["_tb"].sum()


# Stats where a 0 on a played game date is meaningful and must be filled in.
# EV/RBI are aggregations — they handle their own NaN logic.
_ZERO_FILL_STATS = {"H", "HR", "TB", "SO", "K", "BB", "SB"}

STAT_EXTRACTORS = {
    "H":   lambda df: df[df["events"].isin(["single","double","triple","home_run"])].groupby("game_date").size(),
    "HR":  lambda df: df[df["events"] == "home_run"].groupby("game_date").size(),
    "TB":  _tb_from_events,
    "SO":  lambda df: df[df["events"] == "strikeout"].groupby("game_date").size(),
    "K":   lambda df: df[df["events"] == "strikeout"].groupby("game_date").size(),
    "BB":  lambda df: df[df["events"] == "walk"].groupby("game_date").size(),
    "SB":  lambda df: df[df["events"].isin(["stolen_base_2b","stolen_base_3b","stolen_base_home"])].groupby("game_date").size(),
    "EV":  lambda df: df[df["launch_speed"].notna()].groupby("game_date")["launch_speed"].mean().round(1),
    "RBI": lambda df: (
        df[df["events"].notna()].assign(
            _rbi=(df[df["events"].notna()]["post_bat_score"] - df[df["events"].notna()]["bat_score"]).clip(lower=0)
        ).groupby("game_date")["_rbi"].sum()
    ),
}


def fetch_batter_series(name: str, stat: str = "H", num_games: int = 40) -> list[float]:
    """Fetch per-game stat series for a batter. Returns list of values."""
    if not _PYB_OK:
        logging.warning("pybaseball not available")
        return []

    mlbam_id = PLAYER_IDS.get(name.lower().strip())
    if mlbam_id is None:
        logging.warning(f"No MLBAM ID for '{name}'. Add to PLAYER_IDS.")
        return []

    try:
        data = statcast_batter(SEASON_START, SEASON_END, player_id=mlbam_id)
    except Exception as e:
        logging.error(f"Statcast fetch failed for {name}: {e}")
        return []

    if data is None or data.empty:
        return []

    data["game_date"] = pd.to_datetime(data["game_date"])
    stat_upper = stat.upper()
    extractor = STAT_EXTRACTORS.get(stat_upper)
    if extractor is None:
        logging.warning(f"Unknown stat: {stat}")
        return []

    series = extractor(data).sort_index()

    # For counting stats, reindex to all game dates the player appeared so
    # that 0-hit / 0-HR games show up as 0 instead of being silently dropped.
    if stat_upper in _ZERO_FILL_STATS:
        all_game_dates = data["game_date"].drop_duplicates().sort_values()
        series = series.reindex(all_game_dates, fill_value=0)

    values = series.astype(float).tail(num_games).tolist()
    return values


def fetch_pitcher_series(name: str, stat: str = "K", num_games: int = 20) -> list[float]:
    """Fetch per-game K or other stat for a pitcher."""
    if not _PYB_OK:
        return []

    mlbam_id = PLAYER_IDS.get(name.lower().strip())
    if mlbam_id is None:
        logging.warning(f"No MLBAM ID for '{name}'. Add to PLAYER_IDS.")
        return []

    try:
        data = statcast_pitcher(SEASON_START, SEASON_END, player_id=mlbam_id)
    except Exception as e:
        logging.error(f"Statcast fetch failed for {name}: {e}")
        return []

    if data is None or data.empty:
        return []

    data["game_date"] = pd.to_datetime(data["game_date"])
    stat_upper = stat.upper()
    extractor = STAT_EXTRACTORS.get(stat_upper)
    if extractor is None:
        return []

    series = extractor(data).sort_index()

    if stat_upper in _ZERO_FILL_STATS:
        all_game_dates = data["game_date"].drop_duplicates().sort_values()
        series = series.reindex(all_game_dates, fill_value=0)

    return series.astype(float).tail(num_games).tolist()


# ── Shared drawing helpers ────────────────────────────────────────────────────

_WATERMARK_IMG = None

def _stamp_watermark(fig, alpha: float = 0.30, size: float = 0.07) -> None:
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


def _draw_batter_panel(ax, name: str, team: str, values: list[float],
                       stat: str, threshold: float | None = None,
                       game_label: str = ""):
    """Single batter panel: bar chart + line + sliding FSR window."""
    if not values:
        ax.set_facecolor(PANEL)
        ax.text(0.5, 0.5, f"No data\n{name}", transform=ax.transAxes,
                ha="center", va="center", color=SUB, fontsize=9)
        ax.set_title(name, color=TEXT, fontsize=8)
        return

    fsr = calculate_predictability(values, k=0.5)
    n = len(values)
    x = list(range(1, n + 1))
    avg = sum(values) / len(values)

    color = TEAM_COLORS.get(team, (ACCENT, PANEL))[0]

    ax.set_facecolor(PANEL)
    ax.spines[:].set_color(GRID)
    ax.tick_params(colors=SUB, labelsize=7)

    # threshold line
    if threshold is not None:
        ax.axhline(threshold, color=GOLD, linewidth=1.1, linestyle="--", alpha=0.85, zorder=2)
        ax.text(0.02, threshold + max(values) * 0.03,
                f"{threshold:.0f}+ prop", color=GOLD, fontsize=6, alpha=0.9)

    # avg line
    ax.axhline(avg, color=color, linewidth=0.7, linestyle=":", alpha=0.5, zorder=2)

    # bars
    if threshold is not None:
        bar_colors = [ELITE if v >= threshold else DANGER for v in values]
    else:
        bar_colors = [color] * n
    ax.bar(x, values, color=bar_colors, alpha=0.5, width=0.75, zorder=3)
    ax.plot(x, values, color=color, linewidth=1.2, zorder=4)
    ax.scatter(x[-1:], values[-1:], color=color, s=30, zorder=6)

    # sliding window twin axis
    try:
        win_size = max(5, min(10, n // 4))
        win_scores, _ = calculate_sliding_window(values, window_size=win_size)
        win_x = list(range(len(win_scores)))
        ax2 = ax.twinx()
        ax2.set_facecolor("none")
        ax2.spines[:].set_color(GRID)
        ax2.tick_params(colors=SUB, labelsize=6)
        ax2.set_ylim(0, 120)
        ax2.plot(win_x, win_scores, color=ACCENT, linewidth=1.0,
                 linestyle=":", alpha=0.75, zorder=5)
        ax2.set_ylabel("FSR Win.", color=ACCENT, fontsize=5.5)
    except Exception:
        pass

    # FSR badge
    fsr_col = _fsr_color(fsr)
    ax.text(0.98, 0.97, f"FSR  {fsr:.1f}", transform=ax.transAxes,
            ha="right", va="top", fontsize=9, fontweight="bold", color=fsr_col,
            bbox=dict(boxstyle="round,pad=0.3", facecolor=BG, edgecolor=fsr_col, alpha=0.9))

    # avg badge
    ax.text(0.02, 0.97, f"Avg {avg:.2f} {stat}/g", transform=ax.transAxes,
            ha="left", va="top", fontsize=7, color=SUB,
            bbox=dict(boxstyle="round,pad=0.2", facecolor=BG, edgecolor=GRID, alpha=0.8))

    last_n = values[-10:]
    hot = sum(1 for v in last_n if v > avg)
    trend = "HOT" if hot >= 7 else ("COLD" if hot <= 3 else "AVG")
    trend_col = ELITE if trend == "HOT" else (DANGER if trend == "COLD" else SUB)
    ax.text(0.98, 0.04, f"L10: {trend}", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=7, fontweight="bold", color=trend_col,
            bbox=dict(boxstyle="round,pad=0.2", facecolor=BG, edgecolor=trend_col, alpha=0.8))

    display_name = name.title()
    label = f"{game_label}  " if game_label else ""
    ax.set_title(f"{label}{display_name}  [{team}]  —  {stat} per game",
                 color=TEXT, fontsize=8, pad=3)
    ax.set_ylabel(stat, color=SUB, fontsize=7)
    ax.set_xlim(0.5, n + 0.5)
    ax.set_ylim(bottom=0)
    # Use whole-number ticks for counting stats
    FLOAT_STATS = {"EV", "VELO", "LA", "SPIN"}
    if stat.upper() not in FLOAT_STATS:
        ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))


# ── Chart builders ────────────────────────────────────────────────────────────

def build_batter_duel_chart(
    game_label: str,
    away_team: str, away_batters: list[str],
    home_team: str, home_batters: list[str],
    stat: str = "H",
    num_games: int = 40,
    threshold: float | None = None,
    out_path: str = "",
    title_suffix: str = "",
):
    """2-column grid: away batters (left) vs home batters (right)."""
    n_rows = max(len(away_batters), len(home_batters))
    fig, axes = plt.subplots(n_rows, 2, figsize=(14, 4.5 * n_rows), facecolor=BG)
    fig.patch.set_facecolor(BG)

    if n_rows == 1:
        axes = [axes]

    away_col = TEAM_COLORS.get(away_team, (ACCENT, PANEL))[0]
    home_col = TEAM_COLORS.get(home_team, (ACCENT, PANEL))[0]

    header = f"{away_team} @ {home_team}  ·  {stat} Consistency  ·  FSR Batter Duel"
    if title_suffix:
        header += f"  ·  {title_suffix}"
    fig.suptitle(header, color=TEXT, fontsize=13, fontweight="bold", y=0.995)

    # column headers
    fig.text(0.26, 0.993, f"◀  {away_team}  (Away)", ha="center", va="bottom",
             fontsize=10, color=away_col, fontweight="bold")
    fig.text(0.74, 0.993, f"{home_team}  (Home)  ▶", ha="center", va="bottom",
             fontsize=10, color=home_col, fontweight="bold")

    for row in range(n_rows):
        ax_away = axes[row][0] if n_rows > 1 else axes[0][0]
        ax_home = axes[row][1] if n_rows > 1 else axes[0][1]

        if row < len(away_batters):
            name = away_batters[row]
            logging.info(f"  Fetching {name} ({away_team}) {stat}...")
            vals = fetch_batter_series(name, stat=stat, num_games=num_games)
            _draw_batter_panel(ax_away, name, away_team, vals, stat,
                               threshold=threshold, game_label=game_label)
        else:
            ax_away.set_visible(False)

        if row < len(home_batters):
            name = home_batters[row]
            logging.info(f"  Fetching {name} ({home_team}) {stat}...")
            vals = fetch_batter_series(name, stat=stat, num_games=num_games)
            _draw_batter_panel(ax_home, name, home_team, vals, stat,
                               threshold=threshold, game_label=game_label)
        else:
            ax_home.set_visible(False)

    plt.subplots_adjust(hspace=0.45, wspace=0.35,
                        left=0.06, right=0.96, top=0.97, bottom=0.04)
    fig.text(0.5, 0.005,
             "predictability-api.com  ·  @PredictabilityC  ·  FSR = Field Stability Rating™  ·  Data: Statcast 2025",
             ha="center", va="bottom", fontsize=6.5, color=SUB, alpha=0.8)

    _stamp_watermark(fig)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    logging.info(f"Saved → {out_path}")


def build_closer_duel_chart(
    game_label: str,
    away_team: str, away_closer: str,
    home_team: str, home_closer: str,
    stat: str = "K",
    num_games: int = 40,
    out_path: str = "",
):
    """Side-by-side closer K-rate FSR chart."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), facecolor=BG)
    fig.patch.set_facecolor(BG)

    fig.suptitle(
        f"{away_team} @ {home_team}  ·  Closer Duel  ·  {stat} per Outing  ·  FSR",
        color=TEXT, fontsize=12, fontweight="bold", y=1.00,
    )

    away_col = TEAM_COLORS.get(away_team, (ACCENT, PANEL))[0]
    home_col = TEAM_COLORS.get(home_team, (ACCENT, PANEL))[0]

    for ax, name, team in [(axes[0], away_closer, away_team),
                            (axes[1], home_closer, home_team)]:
        logging.info(f"  Fetching closer {name} ({team}) {stat}...")
        vals = fetch_pitcher_series(name, stat=stat, num_games=num_games)
        _draw_batter_panel(ax, name, team, vals, stat,
                           game_label=game_label)

    plt.subplots_adjust(wspace=0.4, left=0.07, right=0.95, top=0.93, bottom=0.08)
    fig.text(0.5, 0.01,
             "predictability-api.com  ·  @PredictabilityC  ·  Data: Statcast 2025",
             ha="center", va="bottom", fontsize=6.5, color=SUB, alpha=0.8)

    _stamp_watermark(fig)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    logging.info(f"Saved → {out_path}")


def build_solo_batter_chart(
    name: str, team: str,
    stats: list[str],
    game_label: str = "",
    num_games: int = 50,
    out_path: str = "",
):
    """Multi-stat chart for a single star player (1 row per stat)."""
    n = len(stats)
    fig, axes = plt.subplots(1, n, figsize=(6.5 * n, 5), facecolor=BG)
    fig.patch.set_facecolor(BG)
    if n == 1:
        axes = [axes]

    color = TEAM_COLORS.get(team, (ACCENT, PANEL))[0]
    fig.suptitle(
        f"{name.title()}  [{team}]  ·  2025 Season Consistency  ·  FSR",
        color=TEXT, fontsize=13, fontweight="bold", y=1.01,
    )
    if game_label:
        fig.text(0.5, 0.99, game_label, ha="center", va="top",
                 fontsize=9, color=SUB)

    for ax, stat in zip(axes, stats):
        logging.info(f"  Fetching {name} {stat}...")
        vals = fetch_batter_series(name, stat=stat, num_games=num_games)
        _draw_batter_panel(ax, name, team, vals, stat, game_label="")

    plt.subplots_adjust(wspace=0.38, left=0.06, right=0.96, top=0.92, bottom=0.08)
    fig.text(0.5, 0.01,
             "predictability-api.com  ·  @PredictabilityC  ·  Data: Statcast 2025",
             ha="center", va="bottom", fontsize=6.5, color=SUB, alpha=0.8)

    _stamp_watermark(fig)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    logging.info(f"Saved → {out_path}")



# ── Bullpen FSR chart ─────────────────────────────────────────────────────────

def build_bullpen_chart(
    game_label: str,
    away_team: str, away_relievers: list[str],
    home_team: str, home_relievers: list[str],
    stat: str = "K",
    num_games: int = 35,
    out_path: str = "",
):
    """Side-by-side bullpen K-consistency FSR chart for two teams.

    Pre-fetches all data, drops players with no results, then builds
    a clean grid with only players who have 2025 Statcast data.
    """
    away_color = TEAM_COLORS.get(away_team, (ACCENT, PANEL))[0]
    home_color  = TEAM_COLORS.get(home_team,  (ACCENT, PANEL))[0]

    # Pre-fetch — filter out players with no data
    def _fetch_side(names, team):
        results = []
        for name in names:
            logging.info(f"  Fetching reliever {name} ({team}) {stat}...")
            vals = fetch_pitcher_series(name, stat=stat, num_games=num_games)
            if vals:
                results.append((name, vals))
            else:
                logging.warning(f"  No 2025 data for {name} — skipping panel")
        return results

    away_data = _fetch_side(away_relievers, away_team)
    home_data  = _fetch_side(home_relievers,  home_team)

    # Need at least 1 reliever per side to draw
    if not away_data and not home_data:
        logging.error(f"No reliever data at all for {away_team}@{home_team} — skipping")
        return

    # Pad shorter side with None so grid is rectangular
    n_rows = max(len(away_data), len(home_data))
    away_padded = away_data + [(None, [])] * (n_rows - len(away_data))
    home_padded  = home_data  + [(None, [])] * (n_rows - len(home_data))

    fig, axes = plt.subplots(n_rows, 2, figsize=(14, 4.2 * n_rows), facecolor=BG)
    fig.patch.set_facecolor(BG)
    if n_rows == 1:
        axes = axes.reshape(1, 2)

    away_all, home_all = [], []

    for col_idx, (team, side_data, color) in enumerate([
        (away_team, away_padded, away_color),
        (home_team,  home_padded,  home_color),
    ]):
        for row_idx, (name, vals) in enumerate(side_data):
            ax = axes[row_idx, col_idx]
            if name is not None:
                if col_idx == 0:
                    away_all.extend(vals)
                else:
                    home_all.extend(vals)
                _draw_batter_panel(ax, name, team, vals, stat)
            else:
                # True blank — matches background, no axes junk
                ax.set_facecolor(BG)
                ax.set_xticks([])
                ax.set_yticks([])
                ax.set_xlim(0, 1)
                ax.set_ylim(0, 1)
                for spine in ax.spines.values():
                    spine.set_visible(False)

    away_fsr = calculate_predictability(away_all, k=0.5) if away_all else 0.0
    home_fsr  = calculate_predictability(home_all,  k=0.5) if home_all else 0.0

    fig.suptitle(
        f"Bullpen K-Rate Consistency  |  {away_team} @ {home_team}",
        color=TEXT, fontsize=14, fontweight="bold",
    )

    away_fsr_col = _fsr_color(away_fsr)
    home_fsr_col  = _fsr_color(home_fsr)
    fig.text(0.27, 0.97, f"{away_team} Bullpen  —  FSR {away_fsr:.1f}",
             ha="center", va="top", fontsize=11, fontweight="bold", color=away_fsr_col)
    fig.text(0.73, 0.97, f"{home_team} Bullpen  —  FSR {home_fsr:.1f}",
             ha="center", va="top", fontsize=11, fontweight="bold", color=home_fsr_col)

    if game_label:
        fig.text(0.5, 0.995, game_label, ha="center", va="top",
                 fontsize=9, color=SUB)

    fig.text(0.5, 0.005,
             "predictability-api.com  |  @PredictabilityC  |  Data: Statcast 2025",
             ha="center", va="bottom", fontsize=6.5, color=SUB, alpha=0.8)

    plt.subplots_adjust(hspace=0.48, wspace=0.32,
                        left=0.06, right=0.96, top=0.92, bottom=0.05)
    _stamp_watermark(fig)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    logging.info(f"Saved -> {out_path}")


# ── Main: tonight's charts ────────────────────────────────────────────────────

def main(game_date: str = "2026-03-26"):
    mm_dd = game_date[5:].replace("-", "-")
    year  = game_date[:4]
    out_dir = os.path.join("static", "images", "mlb_preview", year, mm_dd)
    os.makedirs(out_dir, exist_ok=True)

    # ── 1. Shohei Ohtani solo star chart (HR + H + TB) ────────────────────────
    logging.info("=== Ohtani solo chart ===")
    build_solo_batter_chart(
        name="shohei ohtani", team="LAD",
        stats=["HR", "H", "TB"],
        game_label="ARI @ LAD  ·  Dodger Stadium  ·  8:30 PM ET  (NBC)",
        num_games=50,
        out_path=os.path.join(out_dir, "batter_ohtani_solo.png"),
    )

    # ── 2. ARI @ LAD batter duel — Hits ───────────────────────────────────────
    logging.info("=== ARI @ LAD Batter Duel (H) ===")
    build_batter_duel_chart(
        game_label="ARI @ LAD  8:30 PM",
        away_team="ARI",
        away_batters=["corbin carroll", "ketel marte", "christian walker"],
        home_team="LAD",
        home_batters=["shohei ohtani", "freddie freeman", "mookie betts"],
        stat="H",
        num_games=40,
        out_path=os.path.join(out_dir, "batter_duel_ari_lad_h.png"),
        title_suffix="Dodger Stadium  ·  8:30 PM ET (NBC)",
    )

    # ── 3. ARI @ LAD batter duel — HR ─────────────────────────────────────────
    logging.info("=== ARI @ LAD Batter Duel (HR) ===")
    build_batter_duel_chart(
        game_label="ARI @ LAD  8:30 PM",
        away_team="ARI",
        away_batters=["corbin carroll", "ketel marte", "christian walker"],
        home_team="LAD",
        home_batters=["shohei ohtani", "freddie freeman", "mookie betts"],
        stat="HR",
        num_games=40,
        out_path=os.path.join(out_dir, "batter_duel_ari_lad_hr.png"),
        title_suffix="Dodger Stadium  ·  8:30 PM ET (NBC)",
    )

    # ── 4. CLE @ SEA Closer Duel ──────────────────────────────────────────────
    logging.info("=== CLE @ SEA Closer Duel ===")
    build_closer_duel_chart(
        game_label="CLE @ SEA  10:10 PM",
        away_team="CLE", away_closer="emmanuel clase",
        home_team="SEA", home_closer="andres munoz",
        stat="K",
        num_games=40,
        out_path=os.path.join(out_dir, "closer_duel_cle_sea.png"),
    )

    # ── 5. CLE @ SEA Batter Duel ──────────────────────────────────────────────
    logging.info("=== CLE @ SEA Batter Duel (H) ===")
    build_batter_duel_chart(
        game_label="CLE @ SEA  10:10 PM",
        away_team="CLE",
        away_batters=["jose ramirez", "steven kwan", "josh naylor"],
        home_team="SEA",
        home_batters=["julio rodriguez", "cal raleigh", "jorge polanco"],
        stat="H",
        num_games=40,
        out_path=os.path.join(out_dir, "batter_duel_cle_sea_h.png"),
        title_suffix="T-Mobile Park  ·  10:10 PM ET",
    )

    logging.info("=== All batter charts complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="2026-03-26")
    args = parser.parse_args()
    main(game_date=args.date)
