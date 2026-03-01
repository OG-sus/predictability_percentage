import math
import numpy as np
from numba import jit

@jit(nopython=True)
def calculate_predictability_numba(scores_array, k=1.0):
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

    # SAFETY CHECK: If mean is effectively zero, return 0.0 to avoid division by zero explosion
    if abs(mean_val) < 1e-9:
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
    # Score = 100 * e^(-k * |CV|)
    # We use absolute value of CV because standard deviation is always positive, 
    # but mean can be negative, making CV negative.
    score = 100 * math.exp(-k * abs(cv))
    
    # Clamp score to 0-100 just in case
    if score > 100.0:
        score = 100.0
    if score < 0.0:
        score = 0.0
    
    return score

@jit(nopython=True)
def calculate_deviation_numba(scores_array, target):
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
        return calculate_predictability_numba(scores_array, k)
    except Exception as e:
        # Fallback or error handling
        print(f"Calculation error: {e}")
        return 0.0

def calculate_deviation(scores, target):
    """
    Wrapper for deviation calculation.
    """
    try:
        scores_array = np.array(scores, dtype=np.float64)
        return calculate_deviation_numba(scores_array, float(target))
    except Exception as e:
        print(f"Deviation error: {e}")
        return 0.0
