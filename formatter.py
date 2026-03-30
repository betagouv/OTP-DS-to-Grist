import json

def unwrap_json_list(raw: str) -> str:
    """
    Convertit '["a", "b"]' en 'a, b', laisse les strings normales intactes.
    Nécessaire car les anciennes démarches DS retournent les valeurs de listes
    déroulantes comme chaînes simples, tandis que les nouvelles les retournent
    sous forme de chaînes JSON encodées.
    """
    if isinstance(raw, str) and raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return ", ".join(str(v) for v in parsed)
        except (json.JSONDecodeError, TypeError):
            pass
    return raw
