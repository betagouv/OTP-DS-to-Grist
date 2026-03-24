import json


def unwrap_json_list(raw):
    """Convertit '["a", "b"]' en 'a, b', laisse les strings normales intactes."""
    if isinstance(raw, str) and raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return ", ".join(str(v) for v in parsed)
        except (json.JSONDecodeError, TypeError):
            pass
    return raw
