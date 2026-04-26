import csv
import os
import re

import matplotlib.pyplot as plt

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window


def clean_filename(text):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", text.strip())
    return cleaned.strip("_") or "series_chart"


def coerce_numeric(value):
    raw = str(value).strip().replace(",", "")
    if raw.endswith("%"):
        raw = raw[:-1]
    number = float(raw)
    if number.is_integer():
        return int(number)
    return number


def parse_numeric_series(raw):
    tokens = [token for token in re.split(r"[\s,]+", raw.strip()) if token]
    if len(tokens) < 2:
        raise ValueError("Need at least 2 values.")
    return [coerce_numeric(token) for token in tokens]


def collect_pasted_series():
    print("Paste values separated by commas, spaces, or new lines.")
    print("Press Enter on a blank line when finished.")
    lines = []
    while True:
        line = input().strip()
        if not line:
            break
        lines.append(line)
    return parse_numeric_series("\n".join(lines))


def load_series_from_csv(csv_path, value_column, filter_column="", filter_value=""):
    csv_path = os.path.expanduser(csv_path)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError("CSV is missing a header row.")
        if value_column not in reader.fieldnames:
            raise ValueError(f"Column not found: {value_column}")
        if filter_column and filter_column not in reader.fieldnames:
            raise ValueError(f"Filter column not found: {filter_column}")

        series = []
        for row in reader:
            if filter_column and str(row.get(filter_column, "")).strip() != filter_value:
                continue
            raw_value = str(row.get(value_column, "")).strip()
            if not raw_value:
                continue
            series.append(coerce_numeric(raw_value))

    if len(series) < 2:
        raise ValueError("CSV selection produced fewer than 2 numeric values.")
    return series


def prompt_metric_details(default_name, default_stat):
    name = input(f"Label name [default: {default_name}]: ").strip() or default_name
    stat_label = input(f"Stat label [default: {default_stat}]: ").strip() or default_stat
    unit = input("Unit suffix (optional, e.g. ' %' or ' ms'): ").strip()
    lower_is_better = input("Is lower better for this metric? (y/n, default n): ").strip().lower() == "y"
    filename = f"{clean_filename(name)}_{clean_filename(stat_label)}.png"
    return name, stat_label, unit, lower_is_better, filename


def prompt_manual_series(default_name, default_stat):
    name, stat_label, unit, lower_is_better, filename = prompt_metric_details(default_name, default_stat)
    series = collect_pasted_series()
    return name, stat_label, series, unit, lower_is_better, filename


def prompt_csv_series(default_name, default_stat):
    csv_path = input("CSV path: ").strip()
    value_column = input("Value column: ").strip()
    filter_column = input("Filter column (optional): ").strip()
    filter_value = ""
    if filter_column:
        filter_value = input(f"Value to keep from '{filter_column}': ").strip()
    name, stat_label, unit, lower_is_better, filename = prompt_metric_details(default_name, default_stat or value_column or "Metric")
    series = load_series_from_csv(csv_path, value_column, filter_column, filter_value)
    return name, stat_label, series, unit, lower_is_better, filename


def analyze_series(
    name,
    stat_label,
    series,
    *,
    k,
    out_dir,
    unit="",
    filename=None,
    lower_is_better=False,
    series_color="#1f77b4",
    stability_color="#00b5ad",
    x_axis_label="Observation #",
    window_label="sample",
):
    if not series or len(series) < 2:
        raise ValueError("Need at least 2 values.")

    score = calculate_predictability(series, k=k)
    avg = sum(series) / len(series)
    output = ", ".join(map(str, series))

    print(f"\n--- {name} {stat_label} ---")
    print(f"Series ({len(series)} points): {output}")
    print(f"\nPredictability Score : {score:.2f}")
    print(f"Average              : {avg:.2f}{unit}")
    print(f"\n--- COPY DATA ---\n{output}\n")

    _save_chart(
        name,
        stat_label,
        series,
        avg,
        k=k,
        out_dir=out_dir,
        unit=unit,
        filename=filename,
        lower_is_better=lower_is_better,
        series_color=series_color,
        stability_color=stability_color,
        x_axis_label=x_axis_label,
        window_label=window_label,
    )
    return score


def _save_chart(
    name,
    stat_label,
    series,
    avg,
    *,
    k,
    out_dir,
    unit="",
    filename=None,
    lower_is_better=False,
    series_color="#1f77b4",
    stability_color="#00b5ad",
    x_axis_label="Observation #",
    window_label="sample",
):
    window_size = min(10, len(series) // 2)
    if window_size < 2:
        return

    results = calculate_sliding_window(series, window_size, k=k)
    scores = [None] * (window_size - 1) + [result["score"] for result in results]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    ax1.plot(series, marker="o", linestyle="-", color=series_color, alpha=0.85, label=stat_label)
    ax1.axhline(y=avg, color="gray", linestyle="--", label=f"Avg ({avg:.2f}{unit})")
    ax1.set_title(f"{name} — {stat_label}")
    ax1.set_ylabel(unit or stat_label)
    ax1.set_xlabel(x_axis_label)
    if lower_is_better:
        ax1.invert_yaxis()
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(scores, color=stability_color, linewidth=2, label=f"Predictability ({window_size}-{window_label} window)")
    ax2.axhline(y=80, color="green", linestyle="--", label="Elite Stability")
    ax2.axhline(y=60, color="orange", linestyle="--", label="Volatile")
    ax2.set_title("Stability Analysis")
    ax2.set_ylabel("Score (0-100)")
    ax2.set_xlabel(x_axis_label)
    ax2.set_ylim(0, 105)
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename or f"{clean_filename(name)}_{clean_filename(stat_label)}.png")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    print(f"Chart saved → {path}")
