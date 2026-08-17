import base64
import time
from typing import List, Dict, Any, Callable


def decode_base64_id(base64_id: str) -> str:
    """
    Décode un ID en Base64 utilisé par l'API GraphQL.

    Args:
        base64_id: ID en format Base64

    Returns:
        ID décodé
    """
    try:
        # Décodage Base64
        decoded = base64.b64decode(base64_id).decode('utf-8')

        # Les IDs GraphQL sont souvent de la forme "TypeName:id"
        if ':' in decoded:
            return decoded.split(':')[-1]

        # Extrait juste le nombre si le format est "Champ-123456"
        if '-' in decoded:
            return decoded.split('-')[-1]

        return decoded
    except Exception:
        # Si le décodage échoue, retourne l'ID original
        return base64_id


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
