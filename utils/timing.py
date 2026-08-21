import time
from typing import List, Dict, Any, Callable


# Timing des requêtes API (pour statistiques et debugging)
_timings: List[Dict[str, Any]] = []


def timed(func_name: str, service: str = None) -> Callable:
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                _timings.append({
                    "service": service,
                    "function": func_name,
                    "duration": time.time() - start,
                    "args": args,
                    "kwargs": kwargs
                })
        return wrapper
    return decorator


def get_timings() -> List[Dict[str, Any]]:
    return _timings.copy()
