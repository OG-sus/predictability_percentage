import math
import numpy as np
from numba import jit

@jit(nopython=True)
def _calculate_predictability_numba(scores_array, k=1.0):
    """
    JIT-compiled version of the predictability calculation using Numba.
    This runs at C-speed.
    """
    n = len(scores_array)
    if n < 2:
        return 0.0

    # Calculate Mean
    mean_val = 0.0
    for x in scores_array:
        mean_val += x
    mean_val /= n

    if mean_val == 0:
        return 0.0

    # Calculate Standard Deviation
    variance = 0.0
    for x in scores_array:
        variance += (x - mean_val) ** 2
    variance /= (n - 1) # Sample variance
    stdev = math.sqrt(variance)

    # Coefficient of Variation
    cv = stdev / mean_val

    # Exponential Decay Formula
    score = 100 * math.exp(-k * cv)
    
    return score

@jit(nopython=True)
def _calculate_deviation_numba(scores_array, target):
    """
    Calculates the percentage deviation of the data's mean from a target value.
    Returns a float (e.g., 5.0 for 5% deviation).
    """
    n = len(scores_array)
    if n == 0 or target == 0:
        return 0.0
        
    mean_val = 0.0
    for x in scores_array:
        mean_val += x
    mean_val /= n
    
    # Calculate % deviation
    deviation = ((mean_val - target) / target) * 100.0
    return deviation

def calculate_predictability(scores, k=1.0):
    """
    Wrapper function that handles input conversion and calls the JIT function.
    """
    try:
        # Convert list to numpy array for Numba
        # We specify float64 for precision
        scores_array = np.array(scores, dtype=np.float64)
        
        # Call the compiled function
        return _calculate_predictability_numba(scores_array, k)
    except Exception as e:
        # Fallback or error handling
        # In a library, it's often better to raise an exception than to print.
        raise ValueError(f"Calculation error: {e}") from e


def calculate_deviation(scores, target):
    """
    Wrapper for deviation calculation.
    """
    try:
        scores_array = np.array(scores, dtype=np.float64)
        return _calculate_deviation_numba(scores_array, float(target))
    except Exception as e:
        raise ValueError(f"Deviation error: {e}") from e
