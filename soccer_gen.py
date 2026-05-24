import os

import numpy as np

from series_generator_utils import analyze_series, prompt_csv_series, prompt_manual_series

K_SOCCER = 0.5  # Sports standard
OUT_DIR = os.path.join("static", "images", "soccer_charts")


def synthetic_shots_on_target(n=12, avg=5.0, spread=1.5, seed=None):
    rng = np.random.default_rng(seed)
    values = np.clip(np.round(rng.normal(avg, spread, size=n)), 0, 15).astype(int)
    return values.tolist()


def synthetic_xg_series(n=12, avg=1.6, spread=0.45, seed=None):
    rng = np.random.default_rng(seed)
    values = np.clip(rng.normal(avg, spread, size=n), 0.1, 4.0)
    return [round(float(v), 2) for v in values]


def synthetic_corners(n=12, avg=6.0, spread=1.8, seed=None):
    rng = np.random.default_rng(seed)
    values = np.clip(np.round(rng.normal(avg, spread, size=n)), 0, 18).astype(int)
    return values.tolist()


def synthetic_keeper_saves(n=12, avg=3.0, spread=1.1, seed=None):
    rng = np.random.default_rng(seed)
    values = np.clip(np.round(rng.normal(avg, spread, size=n)), 0, 12).astype(int)
    return values.tolist()


def synthetic_goal_diff(n=12, avg=0.8, spread=1.2, seed=None):
    rng = np.random.default_rng(seed)
    values = np.clip(np.round(rng.normal(avg, spread, size=n)), -4, 5).astype(int)
    return values.tolist()


if __name__ == "__main__":
    print("Soccer Predictability Generator")
    print("===============================")
    print("Modes:")
    print("  1. Paste real stat series manually")
    print("  2. Load real stat series from CSV")
    print("  3. Generate synthetic shots on target")
    print("  4. Generate synthetic xG")
    print("  5. Generate synthetic corners")
    print("  6. Generate synthetic keeper saves")
    print("  7. Generate synthetic goal differential")
    print()

    while True:
        mode = input("Select mode (1-7) or 'q' to quit: ").strip()
        if mode.lower() == "q":
            break

        try:
            if mode == "1":
                name, stat_label, series, unit, lower_is_better, filename = prompt_manual_series("Club or player", "Shots on Target")
                analyze_series(name, stat_label, series, k=K_SOCCER, out_dir=OUT_DIR, unit=unit, filename=filename, lower_is_better=lower_is_better, series_color="#2ca02c", window_label="match")

            elif mode == "2":
                name, stat_label, series, unit, lower_is_better, filename = prompt_csv_series("Club or player", "Metric")
                analyze_series(name, stat_label, series, k=K_SOCCER, out_dir=OUT_DIR, unit=unit, filename=filename, lower_is_better=lower_is_better, series_color="#2ca02c", window_label="match")

            elif mode == "3":
                name = input("Club/player label [default: Club]: ").strip() or "Club"
                n = int(input("Number of matches [default: 12]: ").strip() or "12")
                avg = float(input("Average shots on target [default: 5.0]: ").strip() or "5.0")
                spread = float(input("Spread [default: 1.5]: ").strip() or "1.5")
                analyze_series(name, "Shots on Target", synthetic_shots_on_target(n=n, avg=avg, spread=spread), k=K_SOCCER, out_dir=OUT_DIR, filename=f"{name.replace(' ', '_')}_shots_on_target.png", series_color="#2ca02c", window_label="match")

            elif mode == "4":
                name = input("Club/player label [default: Club]: ").strip() or "Club"
                n = int(input("Number of matches [default: 12]: ").strip() or "12")
                avg = float(input("Average xG [default: 1.6]: ").strip() or "1.6")
                spread = float(input("Spread [default: 0.45]: ").strip() or "0.45")
                analyze_series(name, "Expected Goals", synthetic_xg_series(n=n, avg=avg, spread=spread), k=K_SOCCER, out_dir=OUT_DIR, filename=f"{name.replace(' ', '_')}_xg.png", series_color="#1f77b4", window_label="match")

            elif mode == "5":
                name = input("Club/player label [default: Club]: ").strip() or "Club"
                n = int(input("Number of matches [default: 12]: ").strip() or "12")
                avg = float(input("Average corners [default: 6.0]: ").strip() or "6.0")
                spread = float(input("Spread [default: 1.8]: ").strip() or "1.8")
                analyze_series(name, "Corners", synthetic_corners(n=n, avg=avg, spread=spread), k=K_SOCCER, out_dir=OUT_DIR, filename=f"{name.replace(' ', '_')}_corners.png", series_color="#9467bd", window_label="match")

            elif mode == "6":
                name = input("Keeper/team label [default: Keeper]: ").strip() or "Keeper"
                n = int(input("Number of matches [default: 12]: ").strip() or "12")
                avg = float(input("Average saves [default: 3.0]: ").strip() or "3.0")
                spread = float(input("Spread [default: 1.1]: ").strip() or "1.1")
                analyze_series(name, "Keeper Saves", synthetic_keeper_saves(n=n, avg=avg, spread=spread), k=K_SOCCER, out_dir=OUT_DIR, filename=f"{name.replace(' ', '_')}_keeper_saves.png", series_color="#ff7f0e", window_label="match")

            elif mode == "7":
                name = input("Club label [default: Club]: ").strip() or "Club"
                n = int(input("Number of matches [default: 12]: ").strip() or "12")
                avg = float(input("Average goal differential [default: 0.8]: ").strip() or "0.8")
                spread = float(input("Spread [default: 1.2]: ").strip() or "1.2")
                analyze_series(name, "Goal Differential", synthetic_goal_diff(n=n, avg=avg, spread=spread), k=K_SOCCER, out_dir=OUT_DIR, filename=f"{name.replace(' ', '_')}_goal_diff.png", series_color="#d62728", window_label="match")

            else:
                print("Invalid choice.")
        except (FileNotFoundError, ValueError) as e:
            print(f"Error — {e}")
