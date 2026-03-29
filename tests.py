import unittest
from datetime import date

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window
from weather_compare import aggregate_daily_means, build_sample_labels, calculate_vpd, compare_periods, shift_year_safe

class TestPredictabilityMath(unittest.TestCase):

    def test_perfect_consistency(self):
        """Test that identical numbers give a score of 100%."""
        scores = [10, 10, 10, 10]
        result = calculate_predictability(scores)
        self.assertAlmostEqual(result, 100.0, places=2)

    def test_high_volatility(self):
        """Test that wild swings give a low score."""
        scores = [100, 0, 100, 0] # Mean=50, Stdev=50, CoV=1.0
        # Formula: 100 * e^(-1.0 * 1.0) = 100 * 0.367 = 36.78
        result = calculate_predictability(scores, k=1.0)
        self.assertLess(result, 40.0)

    def test_sensitivity_k(self):
        """Test that higher k penalizes the same data more."""
        scores = [10, 12, 10, 12]
        score_standard = calculate_predictability(scores, k=1.0)
        score_pharma = calculate_predictability(scores, k=15.0)
        
        self.assertLess(score_pharma, score_standard)
        print(f"\nStandard Score: {score_standard:.2f}%")
        print(f"Pharma Score:   {score_pharma:.2f}%")

    def test_sliding_window(self):
        """Test the sliding window logic."""
        scores = [100, 100, 100, 100, 100, 200]
        results = calculate_sliding_window(scores, window_size=5, k=1.0)
        
        # Should have 2 windows
        self.assertEqual(len(results), 2)
        
        # First window [100, 100, 100, 100, 100]
        self.assertAlmostEqual(results[0]['score'], 100.0)
        
        # Second window [100, 100, 100, 100, 200]
        self.assertLess(results[1]['score'], 100.0)


class TestWeatherCompareHelpers(unittest.TestCase):

    def test_scaled_series_keep_same_predictability(self):
        previous = [40.0, 45.0, 50.0, 55.0]
        current = [52.0, 58.5, 65.0, 71.5]
        comparison = compare_periods(previous, current, k=1.0)

        self.assertAlmostEqual(comparison['previous']['cov'], comparison['current']['cov'], places=6)
        self.assertAlmostEqual(comparison['previous']['score'], comparison['current']['score'], places=6)
        self.assertIn('relative spread', comparison['explanation'].lower())

    def test_shift_year_safe_handles_leap_day(self):
        shifted = shift_year_safe(date(2024, 2, 29), years=-1)
        self.assertEqual(shifted, date(2023, 2, 28))

    def test_calculate_vpd_known_example(self):
        vpd = calculate_vpd(30.0, 10.0)
        self.assertAlmostEqual(vpd, 3.82, places=2)

    def test_aggregate_daily_means(self):
        samples = [
            (date(2026, 3, 1), 1.0),
            (date(2026, 3, 1), 3.0),
            (date(2026, 3, 2), 2.0),
        ]
        self.assertEqual(aggregate_daily_means(samples), [2.0, 2.0])

    def test_build_sample_labels_daily(self):
        self.assertEqual(
            build_sample_labels(date(2026, 3, 1), 3, "day"),
            ["2026-03-01", "2026-03-02", "2026-03-03"],
        )

    def test_vpd_explanation_uses_metric_name(self):
        previous = [1.0, 1.2, 1.4, 1.6]
        current = [1.2, 1.44, 1.68, 1.92]
        comparison = compare_periods(previous, current, k=1.0, metric_name="VPD")
        self.assertIn("vpd", comparison["explanation"].lower())

if __name__ == '__main__':
    unittest.main()
