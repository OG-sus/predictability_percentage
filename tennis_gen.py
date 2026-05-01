import os

import numpy as np

from series_generator_utils import analyze_series, prompt_csv_series, prompt_manual_series

K_TENNIS = 0.7
OUT_DIR = os.path.join("static", "images", "tennis_charts")


def synthetic_first_serve_pct(n=20, avg=63.0, spread=4.5, seed=None):
    rng = np.random.default_rng(seed)
    values = np.clip(rng.normal(avg, spread, size=n), 35.0, 85.0)
    return [round(float(v), 1) for v in values]


def synthetic_aces(n=20, avg=8.0, spread=3.0, seed=None):
    rng = np.random.default_rng(seed)
    values = np.clip(np.round(rng.normal(avg, spread, size=n)), 0, 35).astype(int)
    return values.tolist()


def synthetic_break_points_won(n=20, avg=4.0, spread=1.8, seed=None):
    rng = np.random.default_rng(seed)
    values = np.clip(np.round(rng.normal(avg, spread, size=n)), 0, 12).astype(int)
    return values.tolist()


def synthetic_hold_rate(n=20, avg=0.78, spread=0.08, seed=None):
    rng = np.random.default_rng(seed)
    values = np.clip(rng.normal(avg, spread, size=n), 0.35, 0.98)
    return [round(float(v), 3) for v in values]


if __name__ == "__main__":
    print("Tennis Predictability Generator")
    print("===============================")
    print("Modes:")
    print("  1. Paste real stat series manually")
    print("  2. Load real stat series from CSV")
    print("  3. Generate synthetic first-serve %")
    print("  4. Generate synthetic aces")
    print("  5. Generate synthetic break points won")
    print("  6. Generate synthetic hold rate")
    print()

    while True:
        mode = input("Select mode (1-6) or 'q' to quit: ").strip()
        if mode.lower() == "q":
            break

        try:
            if mode == "1":
                name, stat_label, series, unit, lower_is_better, filename = prompt_manual_series("Player", "First Serve %")
                analyze_series(name, stat_label, series, k=K_TENNIS, out_dir=OUT_DIR, unit=unit, filename=filename, lower_is_better=lower_is_better, series_color="#17becf", window_label="match")

            elif mode == "2":
                name, stat_label, series, unit, lower_is_better, filename = prompt_csv_series("Player", "Metric")
                analyze_series(name, stat_label, series, k=K_TENNIS, out_dir=OUT_DIR, unit=unit, filename=filename, lower_is_better=lower_is_better, series_color="#17becf", window_label="match")

            elif mode == "3":
                name = input("Player label [default: Player]: ").strip() or "Player"
                n = int(input("Number of matches [default: 20]: ").strip() or "20")
                avg = float(input("Average first-serve % [default: 63]: ").strip() or "63")
                spread = float(input("Spread [default: 4.5]: ").strip() or "4.5")
                analyze_series(name, "First Serve %", synthetic_first_serve_pct(n=n, avg=avg, spread=spread), k=K_TENNIS, out_dir=OUT_DIR, unit=" %", filename=f"{name.replace(' ', '_')}_first_serve_pct.png", series_color="#17becf", window_label="match")

            elif mode == "4":
                name = input("Player label [default: Player]: ").strip() or "Player"
                n = int(input("Number of matches [default: 20]: ").strip() or "20")
                avg = float(input("Average aces [default: 8]: ").strip() or "8")
                spread = float(input("Spread [default: 3.0]: ").strip() or "3.0")
                analyze_series(name, "Aces", synthetic_aces(n=n, avg=avg, spread=spread), k=K_TENNIS, out_dir=OUT_DIR, filename=f"{name.replace(' ', '_')}_aces.png", series_color="#ff7f0e", window_label="match")

            elif mode == "5":
                name = input("Player label [default: Player]: ").strip() or "Player"
                n = int(input("Number of matches [default: 20]: ").strip() or "20")
                avg = float(input("Average break points won [default: 4]: ").strip() or "4")
                spread = float(input("Spread [default: 1.8]: ").strip() or "1.8")
                analyze_series(name, "Break Points Won", synthetic_break_points_won(n=n, avg=avg, spread=spread), k=K_TENNIS, out_dir=OUT_DIR, filename=f"{name.replace(' ', '_')}_break_points_won.png", series_color="#9467bd", window_label="match")

            elif mode == "6":
                name = input("Player label [default: Player]: ").strip() or "Player"
                n = int(input("Number of matches [default: 20]: ").strip() or "20")
                avg = float(input("Average hold rate [default: 0.78]: ").strip() or "0.78")
                spread = float(input("Spread [default: 0.08]: ").strip() or "0.08")
                analyze_series(name, "Hold Rate", synthetic_hold_rate(n=n, avg=avg, spread=spread), k=K_TENNIS, out_dir=OUT_DIR, unit=" rate", filename=f"{name.replace(' ', '_')}_hold_rate.png", series_color="#2ca02c", window_label="match")

            else:
                print("Invalid choice.")
        except (FileNotFoundError, ValueError) as e:
            print(f"Error — {e}")
