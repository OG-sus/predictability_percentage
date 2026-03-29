"""
weather_compare.py — Year-over-Year Weather Stability Comparison
================================================================
Compare one or more cities across the same date window in consecutive years
using the FSR Predictability Score™. By default this script fetches daily
average temperatures from Open-Meteo. It can also compute hourly VPD from
temperature + relative humidity and read from a CSV fallback.

Examples:
  python weather_compare.py --cities Denver "Los Angeles"
  python weather_compare.py --cities Denver --days 75 --end-date 2026-03-21
  python weather_compare.py --cities Denver --csv weather.csv --city-column city
  python weather_compare.py --cities Denver --metric vpd --days 30
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import re
from datetime import date, datetime, timedelta
from statistics import mean, stdev

import requests

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DEFAULT_CITIES = ["Denver", "Los Angeles"]
DEFAULT_K = 1.0
DEFAULT_DAYS = 60
DEFAULT_UNIT = "fahrenheit"
DEFAULT_WINDOW_SIZE = 7
DEFAULT_VPD_AGGREGATION = "hourly"
CITY_ALIASES = {
    "la": "Los Angeles",
    "los angeles, ca": "Los Angeles",
    "denver, co": "Denver",
}
CSV_TEMP_CANDIDATES = [
    "temperature_2m",
    "temperature_2m_mean",
    "daily_avg_temp",
    "avg_temp",
    "average_temperature",
    "temperature",
    "temp",
    "tavg",
    "mean_temp",
]
CSV_RH_CANDIDATES = [
    "relative_humidity_2m",
    "relative_humidity",
    "humidity",
    "rh",
]
CSV_VPD_CANDIDATES = [
    "vapour_pressure_deficit",
    "vapor_pressure_deficit",
    "vpd",
]


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_observation_date(value: str) -> date:
    cleaned = value.strip()
    normalized = cleaned.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        return datetime.strptime(cleaned[:10], "%Y-%m-%d").date()


def shift_year_safe(target_date: date, years: int = -1) -> date:
    try:
        return target_date.replace(year=target_date.year + years)
    except ValueError:
        # Handles leap day by snapping to Feb 28 in the target year.
        return target_date.replace(month=2, day=28, year=target_date.year + years)


def sanitize_city_name(city: str) -> str:
    return CITY_ALIASES.get(city.strip().lower(), city.strip())


def fahrenheit_to_celsius(temp_f: float) -> float:
    return (temp_f - 32.0) * (5.0 / 9.0)


def calculate_vpd(temp_c: float, rh: float) -> float:
    saturation_vapor_pressure = 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
    actual_vapor_pressure = (rh / 100.0) * saturation_vapor_pressure
    return saturation_vapor_pressure - actual_vapor_pressure


def aggregate_daily_means(samples: list[tuple[date, float]]) -> list[float]:
    grouped: dict[date, list[float]] = {}
    for sample_date, value in samples:
        grouped.setdefault(sample_date, []).append(value)
    return [mean(grouped[sample_date]) for sample_date in sorted(grouped)]


def compute_cov(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = mean(values)
    if abs(avg) < 1e-9:
        return 0.0
    return stdev(values) / avg


def summarize_period(label: str, values: list[float], k: float = DEFAULT_K) -> dict:
    if len(values) < 2:
        raise ValueError(f"{label} needs at least 2 values for analysis.")

    avg = mean(values)
    std_dev = stdev(values)
    cov = compute_cov(values)
    score = calculate_predictability(values, k=k)
    return {
        "label": label,
        "count": len(values),
        "mean": avg,
        "std_dev": std_dev,
        "cov": cov,
        "score": score,
        "values": values,
    }


def compare_periods(
    previous_values: list[float],
    current_values: list[float],
    k: float = DEFAULT_K,
    metric_name: str = "temperature",
) -> dict:
    previous = summarize_period("previous_year", previous_values, k=k)
    current = summarize_period("current_year", current_values, k=k)
    score_delta = current["score"] - previous["score"]
    mean_delta = current["mean"] - previous["mean"]
    mean_delta_pct = 0.0 if abs(previous["mean"]) < 1e-9 else (mean_delta / previous["mean"]) * 100.0
    cov_delta = current["cov"] - previous["cov"]
    explanation = generate_explanation(previous, current, metric_name=metric_name)
    return {
        "previous": previous,
        "current": current,
        "score_delta": score_delta,
        "mean_delta": mean_delta,
        "mean_delta_pct": mean_delta_pct,
        "cov_delta": cov_delta,
        "explanation": explanation,
        "metric_name": metric_name,
    }


def generate_explanation(previous: dict, current: dict, metric_name: str = "temperature") -> str:
    score_delta = current["score"] - previous["score"]
    cov_delta = current["cov"] - previous["cov"]
    mean_delta = current["mean"] - previous["mean"]
    metric_label = metric_name.strip() or "temperature"
    metric_label_title = metric_label[:1].upper() + metric_label[1:]

    if abs(score_delta) <= 1.5 and abs(cov_delta) <= 0.02:
        direction = "upward" if mean_delta > 0 else "downward"
        return (
            f"Average {metric_label} shifted {direction}, but the relative spread stayed almost the same. "
            f"Because FSR is driven by coefficient of variation, the Predictability Score barely moved."
        )

    if score_delta > 1.5 and cov_delta < -0.02:
        return (
            f"{metric_label_title} changed and the day-to-day spread tightened relative to the mean, "
            "so the Predictability Score improved."
        )

    if score_delta < -1.5 and cov_delta > 0.02:
        return (
            f"{metric_label_title} changed and the relative spread widened, so the Predictability Score fell."
        )

    if abs(score_delta) <= 1.5:
        return (
            "The score stayed in the same band even though the distribution shape changed modestly. "
            "The relative variation was not large enough to create a big FSR move."
        )

    return (
        "The year-over-year distribution changed enough to move the coefficient of variation, "
        "so the Predictability Score also moved."
    )


def resolve_city(city: str) -> dict:
    params = {"name": sanitize_city_name(city), "count": 1, "language": "en", "format": "json"}
    response = requests.get(GEOCODE_URL, params=params, timeout=15)
    response.raise_for_status()
    payload = response.json()
    results = payload.get("results", [])
    if not results:
        raise ValueError(f"Could not resolve city '{city}'.")

    hit = results[0]
    label_parts = [hit.get("name")]
    if hit.get("admin1"):
        label_parts.append(hit["admin1"])
    if hit.get("country"):
        label_parts.append(hit["country"])

    return {
        "name": ", ".join(part for part in label_parts if part),
        "latitude": hit["latitude"],
        "longitude": hit["longitude"],
    }


def fetch_daily_average_temperatures(city: str, start_date: date, end_date: date, unit: str = DEFAULT_UNIT) -> tuple[str, list[float]]:
    location = resolve_city(city)
    params = {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "daily": "temperature_2m_mean",
        "temperature_unit": unit,
        "timezone": "auto",
    }
    response = requests.get(ARCHIVE_URL, params=params, timeout=20)
    response.raise_for_status()
    payload = response.json()
    daily = payload.get("daily", {})
    temperatures = daily.get("temperature_2m_mean", [])
    values = [float(value) for value in temperatures if value is not None]
    if len(values) < 2:
        raise ValueError(f"Not enough daily temperature data returned for {location['name']}.")
    return location["name"], values


def fetch_hourly_vpd(
    city: str,
    start_date: date,
    end_date: date,
    aggregation: str = DEFAULT_VPD_AGGREGATION,
) -> tuple[str, list[float]]:
    location = resolve_city(city)
    params = {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "hourly": "temperature_2m,relative_humidity_2m",
        "temperature_unit": "celsius",
        "timezone": "auto",
    }
    response = requests.get(ARCHIVE_URL, params=params, timeout=20)
    response.raise_for_status()
    payload = response.json()
    hourly = payload.get("hourly", {})
    timestamps = hourly.get("time", [])
    temperatures = hourly.get("temperature_2m", [])
    humidities = hourly.get("relative_humidity_2m", [])
    samples = [
        (parse_observation_date(str(timestamp)), calculate_vpd(float(temp_c), float(rh)))
        for timestamp, temp_c, rh in zip(timestamps, temperatures, humidities)
        if timestamp is not None and temp_c is not None and rh is not None
    ]
    values = aggregate_daily_means(samples) if aggregation == "daily" else [value for _, value in samples]
    if len(values) < 2:
        raise ValueError(f"Not enough hourly VPD data returned for {location['name']}.")
    return location["name"], values


def _detect_column(fieldnames: list[str], candidates: list[str], preferred: str | None = None) -> str:
    if preferred and preferred in fieldnames:
        return preferred

    lowered = {name.lower(): name for name in fieldnames}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]

    raise ValueError(f"Could not find a matching column in CSV. Tried: {', '.join(candidates)}")


def load_temperatures_from_csv(
    path: str,
    start_date: date,
    end_date: date,
    city: str | None = None,
    date_column: str = "date",
    temp_column: str | None = None,
    city_column: str = "city",
) -> tuple[str, list[float]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV file not found: {path}")

    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV file is missing headers.")

        fieldnames = reader.fieldnames
        if date_column not in fieldnames:
            raise ValueError(f"CSV is missing the date column '{date_column}'.")
        selected_temp_column = _detect_column(fieldnames, CSV_TEMP_CANDIDATES, preferred=temp_column)

        values: list[tuple[date, float]] = []
        city_match = sanitize_city_name(city) if city else None

        for row in reader:
            row_city = (row.get(city_column) or "").strip()
            if city_match and row_city and sanitize_city_name(row_city).lower() != city_match.lower():
                continue

            row_date = parse_iso_date((row.get(date_column) or "").strip())
            if row_date < start_date or row_date > end_date:
                continue

            raw_temp = (row.get(selected_temp_column) or "").strip()
            if not raw_temp:
                continue
            values.append((row_date, float(raw_temp)))

    values.sort(key=lambda item: item[0])
    series = [value for _, value in values]
    label = city_match or os.path.basename(path)
    if len(series) < 2:
        raise ValueError(f"Not enough CSV data for {label} between {start_date} and {end_date}.")
    return label, series


def load_vpd_from_csv(
    path: str,
    start_date: date,
    end_date: date,
    city: str | None = None,
    date_column: str = "date",
    temp_column: str | None = None,
    rh_column: str | None = None,
    vpd_column: str | None = None,
    city_column: str = "city",
    csv_temp_unit: str = "celsius",
    aggregation: str = DEFAULT_VPD_AGGREGATION,
) -> tuple[str, list[float]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV file not found: {path}")

    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV file is missing headers.")

        fieldnames = reader.fieldnames
        if date_column not in fieldnames:
            raise ValueError(f"CSV is missing the date column '{date_column}'.")

        selected_vpd_column = None
        try:
            selected_vpd_column = _detect_column(fieldnames, CSV_VPD_CANDIDATES, preferred=vpd_column)
        except ValueError:
            selected_vpd_column = None

        selected_temp_column = None
        selected_rh_column = None
        if selected_vpd_column is None:
            selected_temp_column = _detect_column(fieldnames, CSV_TEMP_CANDIDATES, preferred=temp_column)
            selected_rh_column = _detect_column(fieldnames, CSV_RH_CANDIDATES, preferred=rh_column)

        values: list[tuple[date, float]] = []
        city_match = sanitize_city_name(city) if city else None

        for row in reader:
            row_city = (row.get(city_column) or "").strip()
            if city_match and row_city and sanitize_city_name(row_city).lower() != city_match.lower():
                continue

            row_date = parse_observation_date((row.get(date_column) or "").strip())
            if row_date < start_date or row_date > end_date:
                continue

            if selected_vpd_column is not None:
                raw_vpd = (row.get(selected_vpd_column) or "").strip()
                if not raw_vpd:
                    continue
                values.append((row_date, float(raw_vpd)))
                continue

            raw_temp = (row.get(selected_temp_column) or "").strip()
            raw_rh = (row.get(selected_rh_column) or "").strip()
            if not raw_temp or not raw_rh:
                continue

            temp_value = float(raw_temp)
            if csv_temp_unit == "fahrenheit":
                temp_value = fahrenheit_to_celsius(temp_value)
            vpd_value = calculate_vpd(temp_value, float(raw_rh))
            values.append((row_date, vpd_value))

    values.sort(key=lambda item: item[0])
    series = aggregate_daily_means(values) if aggregation == "daily" else [value for _, value in values]
    label = city_match or os.path.basename(path)
    if len(series) < 2:
        raise ValueError(f"Not enough CSV VPD data for {label} between {start_date} and {end_date}.")
    return label, series


def build_periods(end_date: date, days: int) -> dict:
    if days < 2:
        raise ValueError("--days must be at least 2.")

    current_end = end_date
    current_start = end_date - timedelta(days=days - 1)
    previous_start = shift_year_safe(current_start, years=-1)
    previous_end = shift_year_safe(current_end, years=-1)
    return {
        "current_start": current_start,
        "current_end": current_end,
        "previous_start": previous_start,
        "previous_end": previous_end,
    }


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")


def build_sample_labels(start_date: date, count: int, sample_granularity: str) -> list[str]:
    if sample_granularity == "hour":
        start_dt = datetime.combine(start_date, datetime.min.time())
        return [(start_dt + timedelta(hours=index)).isoformat(timespec="minutes") for index in range(count)]
    return [(start_date + timedelta(days=index)).isoformat() for index in range(count)]


def export_series(
    city_label: str,
    periods: dict,
    comparison: dict,
    metric_key: str,
    unit_label: str,
    sample_granularity: str,
    export_path: str | None = None,
) -> str:
    previous_values = comparison["previous"]["values"]
    current_values = comparison["current"]["values"]
    previous_labels = build_sample_labels(periods["previous_start"], len(previous_values), sample_granularity)
    current_labels = build_sample_labels(periods["current_start"], len(current_values), sample_granularity)

    if export_path:
        path = export_path
        out_dir = os.path.dirname(path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
    else:
        out_dir = os.path.join("static", "images", "weather_charts")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{_safe_filename(city_label)}_{_safe_filename(metric_key)}_series.csv")

    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "sample_index",
                "current_period_sample",
                "current_value",
                "previous_period_sample",
                "previous_value",
                "metric_name",
                "unit",
            ]
        )
        for index, (current_label, current_value, previous_label, previous_value) in enumerate(
            zip(current_labels, current_values, previous_labels, previous_values),
            start=1,
        ):
            writer.writerow(
                [
                    index,
                    current_label,
                    f"{current_value:.6f}",
                    previous_label,
                    f"{previous_value:.6f}",
                    metric_key,
                    unit_label,
                ]
            )
    return path


def save_chart(
    city_label: str,
    comparison: dict,
    current_dates: tuple[date, date],
    previous_dates: tuple[date, date],
    window_size: int,
    k: float,
    unit_label: str,
    metric_title: str,
    sample_axis_label: str,
    window_unit_label: str,
) -> str | None:
    previous_values = comparison["previous"]["values"]
    current_values = comparison["current"]["values"]
    if min(len(previous_values), len(current_values)) < max(window_size, 2):
        return None

    import matplotlib.pyplot as plt

    previous_windows = calculate_sliding_window(previous_values, window_size=window_size, k=k)
    current_windows = calculate_sliding_window(current_values, window_size=window_size, k=k)
    previous_scores = [None] * (window_size - 1) + [row["score"] for row in previous_windows]
    current_scores = [None] * (window_size - 1) + [row["score"] for row in current_windows]

    out_dir = os.path.join("static", "images", "weather_charts")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{_safe_filename(city_label)}_weather_compare.png")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8))

    ax1.plot(previous_values, color="#7f8c8d", linewidth=2, label=f"{previous_dates[0]} to {previous_dates[1]}")
    ax1.plot(current_values, color="#e67e22", linewidth=2, label=f"{current_dates[0]} to {current_dates[1]}")
    ax1.axhline(comparison["previous"]["mean"], color="#95a5a6", linestyle="--", linewidth=1)
    ax1.axhline(comparison["current"]["mean"], color="#d35400", linestyle="--", linewidth=1)
    ax1.set_title(f"{city_label} — {metric_title}")
    ax1.set_ylabel(unit_label)
    ax1.grid(True, alpha=0.25)
    ax1.legend()

    ax2.plot(previous_scores, color="#7f8c8d", linewidth=2, label="Previous year score")
    ax2.plot(current_scores, color="#2980b9", linewidth=2, label="Current year score")
    ax2.axhline(80, color="green", linestyle="--", linewidth=1, label="Elite stability")
    ax2.axhline(60, color="orange", linestyle="--", linewidth=1, label="Volatile")
    ax2.set_title(f"Sliding Window Predictability ({window_size}-{window_unit_label} window)")
    ax2.set_ylabel("Score (0-100)")
    ax2.set_xlabel(sample_axis_label)
    ax2.set_ylim(0, 105)
    ax2.grid(True, alpha=0.25)
    ax2.legend()

    plt.tight_layout()
    plt.savefig(path)
    plt.close(fig)
    return path


def print_report(
    city_label: str,
    periods: dict,
    comparison: dict,
    unit_label: str,
    chart_path: str | None,
    metric_title: str,
    metric_label: str,
    sample_label_plural: str,
    series_path: str | None,
) -> None:
    previous = comparison["previous"]
    current = comparison["current"]

    print(f"\n{'=' * 72}")
    print(f"{city_label} — {metric_title} Predictability Comparison")
    print(f"{'=' * 72}")
    print(
        f"Current window  : {periods['current_start']} to {periods['current_end']} "
        f"({current['count']} {sample_label_plural})"
    )
    print(
        f"Previous window : {periods['previous_start']} to {periods['previous_end']} "
        f"({previous['count']} {sample_label_plural})"
    )
    print()
    print(
        f"Current year    : avg {current['mean']:.2f} {unit_label} {metric_label}, "
        f"std {current['std_dev']:.2f}, CoV {current['cov']:.4f}, "
        f"Predictability Score {current['score']:.2f}/100"
    )
    print(
        f"Previous year   : avg {previous['mean']:.2f} {unit_label} {metric_label}, "
        f"std {previous['std_dev']:.2f}, CoV {previous['cov']:.4f}, "
        f"Predictability Score {previous['score']:.2f}/100"
    )
    print(
        f"Delta           : avg {comparison['mean_delta']:+.2f} {unit_label} "
        f"{metric_label} ({comparison['mean_delta_pct']:+.2f}%), "
        f"Predictability Score {comparison['score_delta']:+.2f}, "
        f"CoV {comparison['cov_delta']:+.4f}"
    )
    print()
    print("What is score?  : Predictability Score is the 0-100 FSR stability score, not VPD itself.")
    print(f"What is VPD?    : VPD is the raw weather metric in {unit_label}; the avg above is the average {metric_label}.")
    print("Explanation     :", comparison["explanation"])
    print(
        "Social copy     :",
        f"{city_label} {metric_label} ran higher year over year, but the relative spread barely changed, "
        f"so the Predictability Score held up."
        if abs(comparison["score_delta"]) <= 1.5
        else f"{city_label} saw a real shift in relative {metric_label} variation, which moved the Predictability Score.",
    )
    if chart_path:
        print(f"Chart saved     : {chart_path}")
    if series_path:
        print(f"Series export   : {series_path}")
        print("Calculator use  : Put the `current_value` column in as this year and `previous_value` as last year.")


def analyze_city(args: argparse.Namespace, city: str) -> dict:
    periods = build_periods(args.end_date, args.days)
    if args.metric == "vpd":
        unit_label = "kPa"
        if args.vpd_aggregation == "daily":
            metric_title = "Daily Average Vapor Pressure Deficit (VPD)"
            metric_label = "daily VPD"
            metric_key = "daily_vpd"
            sample_label_plural = "days"
            sample_axis_label = "Day in window"
            window_unit_label = "day"
            sample_granularity = "day"
            window_size = args.window_size or DEFAULT_WINDOW_SIZE
        else:
            metric_title = "Hourly Vapor Pressure Deficit (VPD)"
            metric_label = "hourly VPD"
            metric_key = "hourly_vpd"
            sample_label_plural = "hours"
            sample_axis_label = "Hour in window"
            window_unit_label = "hour"
            sample_granularity = "hour"
            window_size = args.window_size or 24
    else:
        unit_label = "F" if args.unit == "fahrenheit" else "C"
        metric_title = "Daily Average Temperature"
        metric_label = "temperature"
        metric_key = "temperature"
        sample_label_plural = "days"
        sample_axis_label = "Day in window"
        window_unit_label = "day"
        sample_granularity = "day"
        window_size = args.window_size or DEFAULT_WINDOW_SIZE

    if args.csv:
        if args.metric == "vpd":
            city_label, previous_values = load_vpd_from_csv(
                args.csv,
                periods["previous_start"],
                periods["previous_end"],
                city=city,
                date_column=args.date_column,
                temp_column=args.temp_column,
                rh_column=args.rh_column,
                vpd_column=args.vpd_column,
                city_column=args.city_column,
                csv_temp_unit=args.csv_temp_unit,
                aggregation=args.vpd_aggregation,
            )
            _, current_values = load_vpd_from_csv(
                args.csv,
                periods["current_start"],
                periods["current_end"],
                city=city,
                date_column=args.date_column,
                temp_column=args.temp_column,
                rh_column=args.rh_column,
                vpd_column=args.vpd_column,
                city_column=args.city_column,
                csv_temp_unit=args.csv_temp_unit,
                aggregation=args.vpd_aggregation,
            )
        else:
            city_label, previous_values = load_temperatures_from_csv(
                args.csv,
                periods["previous_start"],
                periods["previous_end"],
                city=city,
                date_column=args.date_column,
                temp_column=args.temp_column,
                city_column=args.city_column,
            )
            _, current_values = load_temperatures_from_csv(
                args.csv,
                periods["current_start"],
                periods["current_end"],
                city=city,
                date_column=args.date_column,
                temp_column=args.temp_column,
                city_column=args.city_column,
            )
    else:
        if args.metric == "vpd":
            city_label, previous_values = fetch_hourly_vpd(
                city,
                periods["previous_start"],
                periods["previous_end"],
                aggregation=args.vpd_aggregation,
            )
            _, current_values = fetch_hourly_vpd(
                city,
                periods["current_start"],
                periods["current_end"],
                aggregation=args.vpd_aggregation,
            )
        else:
            city_label, previous_values = fetch_daily_average_temperatures(
                city, periods["previous_start"], periods["previous_end"], unit=args.unit
            )
            _, current_values = fetch_daily_average_temperatures(
                city, periods["current_start"], periods["current_end"], unit=args.unit
            )

    comparison = compare_periods(previous_values, current_values, k=args.k, metric_name=metric_label)
    series_path = export_series(
        city_label,
        periods,
        comparison,
        metric_key=metric_key,
        unit_label=unit_label,
        sample_granularity=sample_granularity,
        export_path=args.export_series_path,
    ) if args.export_series or args.export_series_path else None
    chart_path = None if args.no_chart else save_chart(
        city_label,
        comparison,
        (periods["current_start"], periods["current_end"]),
        (periods["previous_start"], periods["previous_end"]),
        window_size=min(window_size, len(previous_values), len(current_values)),
        k=args.k,
        unit_label=unit_label,
        metric_title=metric_title,
        sample_axis_label=sample_axis_label,
        window_unit_label=window_unit_label,
    )
    print_report(
        city_label,
        periods,
        comparison,
        unit_label,
        chart_path,
        metric_title,
        metric_label,
        sample_label_plural,
        series_path,
    )
    return comparison


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare year-over-year weather predictability for one or more cities.")
    parser.add_argument("--cities", nargs="+", default=DEFAULT_CITIES, help="City names to analyze.")
    parser.add_argument("--metric", choices=["temperature", "vpd"], default="temperature", help="Metric to compare.")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="Number of days in each comparison window.")
    parser.add_argument(
        "--end-date",
        type=parse_iso_date,
        default=date.today(),
        help="Current window end date in YYYY-MM-DD format (default: today).",
    )
    parser.add_argument("--unit", choices=["fahrenheit", "celsius"], default=DEFAULT_UNIT)
    parser.add_argument("--k", type=float, default=DEFAULT_K, help="FSR k-factor (default: 1.0).")
    parser.add_argument("--window-size", type=int, default=None, help="Sliding window size for charting. Defaults to 7 for temperature, 24 for hourly VPD, and 7 for daily VPD.")
    parser.add_argument("--csv", help="Optional CSV fallback path.")
    parser.add_argument("--date-column", default="date", help="CSV date column name.")
    parser.add_argument("--temp-column", default=None, help="CSV temperature column name.")
    parser.add_argument("--rh-column", default=None, help="CSV relative humidity column name for VPD mode.")
    parser.add_argument("--vpd-column", default=None, help="CSV VPD column name if VPD is already precomputed.")
    parser.add_argument("--csv-temp-unit", choices=["celsius", "fahrenheit"], default="celsius", help="Temperature unit for CSV VPD inputs.")
    parser.add_argument("--vpd-aggregation", choices=["hourly", "daily"], default=DEFAULT_VPD_AGGREGATION, help="For VPD mode, use raw hourly values or collapse them to daily averages for cleaner social charts.")
    parser.add_argument("--city-column", default="city", help="CSV city column name.")
    parser.add_argument("--export-series", action="store_true", help="Export the raw current/previous series to CSV for your calculator.")
    parser.add_argument("--export-series-path", default=None, help="Optional output CSV path for the exported series.")
    parser.add_argument("--no-chart", action="store_true", help="Skip chart generation.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    for city in args.cities:
        analyze_city(args, city)


if __name__ == "__main__":
    main()
