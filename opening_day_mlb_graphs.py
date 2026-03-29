from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import date, timedelta

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from pybaseball import playerid_lookup, statcast_batter, statcast_pitcher

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window
from weather_compare import fetch_hourly_vpd

OUTPUT_DIR = os.path.join("static", "images", "mlb_preview")
SEASON_START = "2025-03-01"
SEASON_END = "2025-11-30"
SPORTS_K = 0.5

BG_COLOR = "#0f1117"
PANEL_COLOR = "#171b24"
GRID_COLOR = "#2b3442"
TEXT_COLOR = "#f5f7fa"
SUBTEXT_COLOR = "#aab6c4"
YANKEES_COLOR = "#8fb3ff"
GIANTS_COLOR = "#ff8c42"
ACCENT_COLOR = "#39c2ff"
HIGHLIGHT_COLOR = "#ffd166"
WEATHER_K = 1.0

PARK_HR_SPLITS = {
    "Oracle Park": {"color": GIANTS_COLOR, "signed_values": [-24, -24, -26]},
    "Yankee Stadium": {"color": YANKEES_COLOR, "signed_values": [19, 15, 27]},
}

PARK_HR_FACTORS = [
    {"team": "ARI", "park": "Chase Field", "hr_factor_pct": -2},
    {"team": "ATL", "park": "Truist Park", "hr_factor_pct": -4},
    {"team": "BAL", "park": "Oriole Park at Camden Yards", "hr_factor_pct": 11},
    {"team": "BOS", "park": "Fenway Park", "hr_factor_pct": -16},
    {"team": "CHC", "park": "Wrigley Field", "hr_factor_pct": 3},
    {"team": "CHW", "park": "Rate Field", "hr_factor_pct": 24},
    {"team": "CIN", "park": "Great American Ball Park", "hr_factor_pct": 27},
    {"team": "CLE", "park": "Progressive Field", "hr_factor_pct": -4},
    {"team": "COL", "park": "Coors Field", "hr_factor_pct": 6},
    {"team": "DET", "park": "Comerica Park", "hr_factor_pct": -4},
    {"team": "HOU", "park": "Daikin Park", "hr_factor_pct": 10},
    {"team": "KC", "park": "Kauffman Stadium", "hr_factor_pct": -17},
    {"team": "LAA", "park": "Angel Stadium", "hr_factor_pct": 2},
    {"team": "LAD", "park": "Dodger Stadium", "hr_factor_pct": 12},
    {"team": "MIA", "park": "loanDepot park", "hr_factor_pct": -15},
    {"team": "MIL", "park": "American Family Field", "hr_factor_pct": 14},
    {"team": "MIN", "park": "Target Field", "hr_factor_pct": -6},
    {"team": "NYM", "park": "Citi Field", "hr_factor_pct": 7},
    {"team": "NYY", "park": "Yankee Stadium", "hr_factor_pct": 19},
    {"team": "PHI", "park": "Citizens Bank Park", "hr_factor_pct": 18},
    {"team": "PIT", "park": "PNC Park", "hr_factor_pct": -17},
    {"team": "SD", "park": "Petco Park", "hr_factor_pct": 2},
    {"team": "SEA", "park": "T-Mobile Park", "hr_factor_pct": -1},
    {"team": "SF", "park": "Oracle Park", "hr_factor_pct": -24},
    {"team": "STL", "park": "Busch Stadium", "hr_factor_pct": -14},
    {"team": "TB", "park": "George M. Steinbrenner Field", "hr_factor_pct": -4},
    {"team": "TEX", "park": "Globe Life Field", "hr_factor_pct": 6},
    {"team": "TOR", "park": "Rogers Centre", "hr_factor_pct": 10},
    {"team": "WAS", "park": "Nationals Park", "hr_factor_pct": -1},
]


@dataclass
class PlayerSeries:
    name: str
    dates: list[str]
    primary: list[float]
    secondary: list[float]
    primary_label: str
    secondary_label: str
    primary_color: str


def _ensure_output_dir() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _style_axes(ax: plt.Axes) -> None:
    ax.set_facecolor(PANEL_COLOR)
    ax.grid(True, alpha=0.12, color=GRID_COLOR)
    ax.tick_params(colors=SUBTEXT_COLOR)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRID_COLOR)
    ax.spines["bottom"].set_color(GRID_COLOR)


def _finish_figure(fig: plt.Figure, path: str) -> str:
    fig.patch.set_facecolor(BG_COLOR)
    plt.tight_layout()
    fig.savefig(path, facecolor=BG_COLOR, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


def _lookup_mlbam_id(player_name: str) -> int:
    parts = player_name.strip().split()
    if len(parts) < 2:
        raise ValueError(f"Player name must include first and last name: {player_name}")
    first, last = parts[0], parts[-1]
    lookup = playerid_lookup(last, first)
    if lookup.empty:
        raise ValueError(f"Could not find MLBAM ID for {player_name}")
    lookup = lookup.sort_values("mlb_played_last", ascending=False)
    return int(lookup.iloc[0]["key_mlbam"])


def _predictability_label(values: list[float]) -> str:
    if len(values) < 2:
        return "n/a"
    return f"{calculate_predictability(values, k=SPORTS_K):.1f}"


def fetch_pitcher_series(player_name: str, num_starts: int = 12, color: str = ACCENT_COLOR) -> PlayerSeries:
    mlbam_id = _lookup_mlbam_id(player_name)
    raw = statcast_pitcher(SEASON_START, SEASON_END, player_id=mlbam_id)
    if raw is None or raw.empty:
        raise ValueError(f"No Statcast pitching data returned for {player_name}")

    frame = raw.copy()
    frame["game_date"] = pd.to_datetime(frame["game_date"])

    strikeouts = (
        frame[frame["events"] == "strikeout"]
        .groupby("game_date")
        .size()
        .rename("strikeouts")
    )
    velocity = (
        frame[frame["release_speed"].notna()]
        .groupby("game_date")["release_speed"]
        .mean()
        .round(1)
        .rename("avg_velocity")
    )

    merged = pd.concat([strikeouts, velocity], axis=1).fillna({"strikeouts": 0})
    merged = merged.dropna(subset=["avg_velocity"]).sort_index().tail(num_starts)
    if merged.empty:
        raise ValueError(f"Not enough per-start data to chart {player_name}")

    return PlayerSeries(
        name=player_name,
        dates=[stamp.strftime("%m-%d") for stamp in merged.index],
        primary=merged["strikeouts"].astype(float).tolist(),
        secondary=merged["avg_velocity"].astype(float).tolist(),
        primary_label="Strikeouts per start",
        secondary_label="Average release velocity",
        primary_color=color,
    )


def fetch_batter_series(player_name: str, num_games: int = 20, color: str = ACCENT_COLOR) -> PlayerSeries:
    mlbam_id = _lookup_mlbam_id(player_name)
    raw = statcast_batter(SEASON_START, SEASON_END, player_id=mlbam_id)
    if raw is None or raw.empty:
        raise ValueError(f"No Statcast batting data returned for {player_name}")

    frame = raw.copy()
    frame["game_date"] = pd.to_datetime(frame["game_date"])

    hits = (
        frame[frame["events"].isin(["single", "double", "triple", "home_run"])]
        .groupby("game_date")
        .size()
        .rename("hits")
    )
    exit_velocity = (
        frame[frame["launch_speed"].notna()]
        .groupby("game_date")["launch_speed"]
        .mean()
        .round(1)
        .rename("avg_ev")
    )

    merged = pd.concat([hits, exit_velocity], axis=1).fillna({"hits": 0})
    merged = merged.dropna(subset=["avg_ev"]).sort_index().tail(num_games)
    if merged.empty:
        raise ValueError(f"Not enough per-game data to chart {player_name}")

    return PlayerSeries(
        name=player_name,
        dates=[stamp.strftime("%m-%d") for stamp in merged.index],
        primary=merged["hits"].astype(float).tolist(),
        secondary=merged["avg_ev"].astype(float).tolist(),
        primary_label="Hits per game",
        secondary_label="Average exit velocity",
        primary_color=color,
    )


def save_san_francisco_vpd_chart(end_date: date, days: int = 30) -> str:
    start_date = end_date - timedelta(days=days - 1)
    _, values = fetch_hourly_vpd("San Francisco", start_date, end_date, aggregation="daily")
    series = pd.Series(values)
    labels = [(start_date + timedelta(days=index)).strftime("%m-%d") for index in range(len(values))]
    overall_score = calculate_predictability(values, k=WEATHER_K)
    window_size = min(7, len(values))
    windows = calculate_sliding_window(values, window_size=window_size, k=WEATHER_K)
    scores = [None] * (window_size - 1) + [row["score"] for row in windows]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12.5, 7.6))
    _style_axes(ax1)
    _style_axes(ax2)

    ax1.plot(labels, values, color=ACCENT_COLOR, linewidth=2.4, marker="o", markersize=3.8, label="Daily VPD")
    ax1.axhline(series.mean(), color=HIGHLIGHT_COLOR, linestyle="--", linewidth=1.3, label=f"Avg: {series.mean():.2f} kPa")
    ax1.set_title("SAN FRANCISCO AIR STABILITY", color=TEXT_COLOR, fontsize=16, pad=10, fontweight="bold")
    ax1.set_ylabel("VPD (kPa)", color=TEXT_COLOR)
    ax1.legend(facecolor=PANEL_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, framealpha=0.6)
    ax1.tick_params(axis="x", rotation=45)
    ax1.text(
        0.02,
        0.95,
        "FSR applies to day-to-day VPD stability entering first pitch.",
        transform=ax1.transAxes,
        ha="left",
        va="top",
        color=SUBTEXT_COLOR,
        fontsize=10,
    )
    ax1.text(
        0.98,
        0.92,
        f"FSR {overall_score:.1f}",
        transform=ax1.transAxes,
        ha="right",
        va="top",
        color=TEXT_COLOR,
        fontsize=18,
        fontweight="bold",
        bbox={"boxstyle": "round,pad=0.35", "facecolor": ACCENT_COLOR, "edgecolor": "none", "alpha": 0.95},
    )

    ax2.axhspan(80, 100, color="#103b2e", alpha=0.22)
    ax2.axhspan(60, 80, color="#4b3d12", alpha=0.16)
    ax2.plot(labels, scores, linewidth=2.3, color=ACCENT_COLOR, label=f"Predictability ({window_size}-day window)")
    ax2.axhline(overall_score, color=ACCENT_COLOR, linestyle="--", linewidth=1.2, label=f"Overall: {overall_score:.1f}")
    ax2.axhline(80, color="#00ff88", linestyle=":", linewidth=1, label="Elite (80)")
    ax2.axhline(60, color="#ffaa00", linestyle=":", linewidth=1, label="Volatile (60)")
    ax2.set_title("FSR PREDICTABILITY SCORE", color=TEXT_COLOR, fontsize=14, pad=10, fontweight="bold")
    ax2.set_ylabel("Score (0-100)", color=TEXT_COLOR)
    ax2.set_xlabel("Date", color=TEXT_COLOR)
    ax2.set_ylim(0, 105)
    ax2.legend(facecolor=PANEL_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, framealpha=0.6)
    ax2.tick_params(axis="x", rotation=45)

    path = os.path.join(OUTPUT_DIR, "san_francisco_vpd_opening_day.png")
    return _finish_figure(fig, path)


def save_oracle_park_chart() -> str:
    split_labels = ["All", "RHB", "LHB"]
    oracle_signed = PARK_HR_SPLITS["Oracle Park"]["signed_values"]
    yankee_signed = PARK_HR_SPLITS["Yankee Stadium"]["signed_values"]
    oracle_score = calculate_predictability([abs(value) for value in oracle_signed], k=WEATHER_K)
    yankee_score = calculate_predictability([abs(value) for value in yankee_signed], k=WEATHER_K)

    fig, ax = plt.subplots(figsize=(11.8, 6.2))
    _style_axes(ax)

    positions = list(range(len(split_labels)))
    width = 0.32
    ax.bar([x - width / 2 for x in positions], oracle_signed, width=width, color=GIANTS_COLOR, label="Oracle Park")
    ax.bar([x + width / 2 for x in positions], yankee_signed, width=width, color=YANKEES_COLOR, label="Yankee Stadium")
    ax.axhline(0, color="#d8dee9", linewidth=1.1)
    ax.set_xticks(positions)
    ax.set_xticklabels(split_labels, color=SUBTEXT_COLOR, fontsize=12)
    ax.set_title("ORACLE PARK SUPPRESSES HR POWER", color=TEXT_COLOR, fontsize=18, pad=12, fontweight="bold")
    ax.set_ylabel("HR factor vs league average (%)", color=TEXT_COLOR)
    ax.legend(facecolor=PANEL_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, framealpha=0.6, loc="lower right")
    ax.text(
        0.02,
        0.95,
        f"Oracle FSR {oracle_score:.1f}",
        transform=ax.transAxes,
        ha="left",
        va="top",
        color=TEXT_COLOR,
        fontsize=14,
        fontweight="bold",
        bbox={"boxstyle": "round,pad=0.3", "facecolor": GIANTS_COLOR, "edgecolor": "none", "alpha": 0.95},
    )
    ax.text(
        0.98,
        0.95,
        f"Yankee FSR {yankee_score:.1f}",
        transform=ax.transAxes,
        ha="right",
        va="top",
        color=TEXT_COLOR,
        fontsize=14,
        fontweight="bold",
        bbox={"boxstyle": "round,pad=0.3", "facecolor": YANKEES_COLOR, "edgecolor": "none", "alpha": 0.95},
    )

    path = os.path.join(OUTPUT_DIR, "oracle_park_hr_context.png")
    return _finish_figure(fig, path)


def _plot_predictability_panel(
    ax_series: plt.Axes,
    ax_score: plt.Axes,
    name: str,
    values: list[float],
    labels: list[str],
    color: str,
    metric_label: str,
    x_label: str,
) -> None:
    average = sum(values) / len(values)
    overall_score = calculate_predictability(values, k=SPORTS_K)
    window_size = min(5, len(values))
    windows = calculate_sliding_window(values, window_size=window_size, k=SPORTS_K)
    scores = [None] * (window_size - 1) + [row["score"] for row in windows]

    ax_series.plot(labels, values, marker="o", markersize=4.5, linewidth=2.6, color=color, alpha=0.95, label=metric_label)
    ax_series.axhline(average, color=HIGHLIGHT_COLOR, linestyle="--", linewidth=1.4, label=f"Avg: {average:.2f}")
    ax_series.set_title(metric_label, color=TEXT_COLOR, fontsize=13, pad=10)
    ax_series.set_ylabel(metric_label, color=TEXT_COLOR)
    ax_series.legend(facecolor=PANEL_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, framealpha=0.6)
    ax_series.tick_params(axis="x", rotation=45)
    ax_series.text(
        0.02,
        0.95,
        name.upper(),
        transform=ax_series.transAxes,
        ha="left",
        va="top",
        color=color,
        fontsize=16,
        fontweight="bold",
    )
    ax_series.text(
        0.98,
        0.92,
        f"FSR {overall_score:.1f}",
        transform=ax_series.transAxes,
        ha="right",
        va="top",
        color=TEXT_COLOR,
        fontsize=16,
        fontweight="bold",
        bbox={"boxstyle": "round,pad=0.35", "facecolor": color, "edgecolor": "none", "alpha": 0.95},
    )
    ax_series.text(
        0.98,
        0.80,
        f"AVG {average:.2f}",
        transform=ax_series.transAxes,
        ha="right",
        va="top",
        color=TEXT_COLOR,
        fontsize=11,
        fontweight="bold",
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "#202634", "edgecolor": GRID_COLOR, "alpha": 0.95},
    )

    ax_score.axhspan(80, 100, color="#103b2e", alpha=0.22)
    ax_score.axhspan(60, 80, color="#4b3d12", alpha=0.16)
    ax_score.plot(labels, scores, linewidth=2.2, color=ACCENT_COLOR, label=f"Predictability ({window_size}-game window)")
    ax_score.axhline(overall_score, color=color, linestyle="--", linewidth=1.1, label=f"Overall: {overall_score:.1f}")
    ax_score.axhline(80, color="#00ff88", linestyle=":", linewidth=1, label="Elite (80)")
    ax_score.axhline(60, color="#ffaa00", linestyle=":", linewidth=1, label="Volatile (60)")
    ax_score.set_title("FSR Predictability Score", color=TEXT_COLOR, fontsize=13, pad=10)
    ax_score.set_ylabel("Score (0-100)", color=TEXT_COLOR)
    ax_score.set_xlabel(x_label, color=TEXT_COLOR)
    ax_score.set_ylim(0, 105)
    ax_score.legend(facecolor=PANEL_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, framealpha=0.6)
    ax_score.tick_params(axis="x", rotation=45)


def _save_dual_predictability_chart(
    left_name: str,
    left_values: list[float],
    left_labels: list[str],
    left_color: str,
    right_name: str,
    right_values: list[float],
    right_labels: list[str],
    right_color: str,
    metric_label: str,
    title: str,
    x_label: str,
    path: str,
) -> str:
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 8.5))
    for ax in axes.flatten():
        _style_axes(ax)

    _plot_predictability_panel(axes[0][0], axes[1][0], left_name, left_values, left_labels, left_color, metric_label, x_label)
    _plot_predictability_panel(axes[0][1], axes[1][1], right_name, right_values, right_labels, right_color, metric_label, x_label)

    fig.suptitle(title, color=TEXT_COLOR, fontsize=18, y=0.995, fontweight="bold")
    fig.text(
        0.5,
        0.955,
        "OPENING DAY EDGE",
        ha="center",
        color=HIGHLIGHT_COLOR,
        fontsize=12,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.015,
        "Premium FSR view: raw series + average on top, sliding Predictability Score below.",
        ha="center",
        color=SUBTEXT_COLOR,
        fontsize=10,
    )
    return _finish_figure(fig, path)


def save_pitcher_comparison_chart() -> str:
    webb = fetch_pitcher_series("Logan Webb", color=GIANTS_COLOR)
    fried = fetch_pitcher_series("Max Fried", color=YANKEES_COLOR)
    return _save_dual_predictability_chart(
        left_name="Max Fried",
        left_values=fried.primary,
        left_labels=fried.dates,
        left_color=YANKEES_COLOR,
        right_name="Logan Webb",
        right_values=webb.primary,
        right_labels=webb.dates,
        right_color=GIANTS_COLOR,
        metric_label="Strikeouts per start",
        title="Max Fried vs Logan Webb — Strikeout Predictability",
        x_label="2025 start date",
        path=os.path.join(OUTPUT_DIR, "fried_vs_webb_opening_day.png"),
    )


def save_hitter_comparison_chart() -> str:
    judge = fetch_batter_series("Aaron Judge", color=YANKEES_COLOR)
    chapman = fetch_batter_series("Matt Chapman", color=GIANTS_COLOR)
    return _save_dual_predictability_chart(
        left_name="Aaron Judge",
        left_values=judge.secondary,
        left_labels=judge.dates,
        left_color=YANKEES_COLOR,
        right_name="Matt Chapman",
        right_values=chapman.secondary,
        right_labels=chapman.dates,
        right_color=GIANTS_COLOR,
        metric_label="Average exit velocity",
        title="Aaron Judge vs Matt Chapman — Exit Velocity Predictability",
        x_label="2025 game date",
        path=os.path.join(OUTPUT_DIR, "judge_vs_chapman_opening_day.png"),
    )


def generate_opening_day_graphs(end_date: date | None = None) -> list[str]:
    _ensure_output_dir()
    # Default to opening night date so charts always end on 3/25 regardless of local timezone
    target_date = end_date or date(2026, 3, 25)
    paths = [
        save_san_francisco_vpd_chart(target_date),
        save_oracle_park_chart(),
        save_pitcher_comparison_chart(),
        save_hitter_comparison_chart(),
    ]
    return paths


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Opening Day MLB preview charts.")
    parser.add_argument(
        "--game-date",
        default=None,
        help="Opening Day date in YYYY-MM-DD format. Defaults to today.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    target_date = date.fromisoformat(args.game_date) if args.game_date else None
    generated_paths = generate_opening_day_graphs(target_date)
    print("Opening Day MLB preview charts generated:")
    for generated_path in generated_paths:
        print(f" - {generated_path}")
