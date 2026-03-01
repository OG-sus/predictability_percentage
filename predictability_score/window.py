from collections import deque
from .core import calculate_predictability, calculate_deviation
import itertools

def sliding_window_generator(scores, window_size, k=1.0, target_value=None):
    """
    A generator that yields predictability scores and deviation for a sliding window.
    """
    window = deque(maxlen=window_size)
    iterator = iter(scores)
    
    for _ in range(window_size):
        try:
            window.append(next(iterator))
        except StopIteration:
            return

    current_window_data = list(window)
    result = {
        'index': 0,
        'window_start': 1,
        'window_end': window_size,
        'score': calculate_predictability(current_window_data, k=k),
        'data': current_window_data
    }
    if target_value is not None:
        result['deviation'] = calculate_deviation(current_window_data, target_value)
    yield result

    for i, new_value in enumerate(iterator, 1):
        window.append(new_value)
        current_window_data = list(window)
        
        result = {
            'index': i,
            'window_start': i + 1,
            'window_end': i + window_size,
            'score': calculate_predictability(current_window_data, k=k),
            'data': current_window_data
        }
        if target_value is not None:
            result['deviation'] = calculate_deviation(current_window_data, target_value)
        yield result

def calculate_sliding_window(scores, window_size, k=1.0, target_value=None):
    """
    Wrapper function to consume the generator and return a list.
    """
    if not scores or window_size <= 0 or window_size > len(scores):
        return []
        
    return list(sliding_window_generator(scores, window_size, k, target_value))
