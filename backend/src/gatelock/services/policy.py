from datetime import time


def in_window(t: time, start: time, end: time) -> bool:
    """True if local time t falls in [start, end). start == end means all day."""
    if start == end:
        return True
    if start < end:
        return start <= t < end
    return t >= start or t < end  # window crosses midnight
