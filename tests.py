import unittest
from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

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

if __name__ == '__main__':
    unittest.main()
