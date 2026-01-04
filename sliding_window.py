from collections import deque
from fsr import calculate_predictability
import itertools

def sliding_window_generator(scores, window_size, k=1.0):
    """
    A generator that yields predictability scores for a sliding window.
    This is memory efficient as it uses a deque and yields results one by one.
    """
    # Create a deque with a fixed maximum length
    window = deque(maxlen=window_size)
    
    # Create an iterator from the scores to handle large streams/lists
    iterator = iter(scores)
    
    # Fill the window initially
    for _ in range(window_size):
        try:
            window.append(next(iterator))
        except StopIteration:
            # Not enough data for even one window
            return

    # Yield the first window's score
    # We convert deque to list for the calculation function, but this is a small list (size N)
    yield {
        'index': 0,
        'window_start': 1,
        'window_end': window_size,
        'score': calculate_predictability(list(window), k=k)
    }

    # Process the rest of the stream
    for i, new_value in enumerate(iterator, 1):
        window.append(new_value) # Automatically pops the oldest value
        
        yield {
            'index': i,
            'window_start': i + 1,
            'window_end': i + window_size,
            'score': calculate_predictability(list(window), k=k)
        }

def calculate_sliding_window(scores, window_size, k=1.0):
    """
    Wrapper function to consume the generator and return a list.
    For API responses, we eventually need a list, but the internal processing is efficient.
    """
    if not scores or window_size <= 0 or window_size > len(scores):
        return []
        
    # Consume the generator into a list
    return list(sliding_window_generator(scores, window_size, k))
