import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def to_local_iso(
    value: datetime | None,
    tz_name: str = "Europe/Paris"
) -> str | None:
    """
    Convertit un datetime UTC (aware ou naïf) en heure locale au format ISO, sans
    fuseau. Le front l'affiche directement comme heure locale.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(ZoneInfo(tz_name)).replace(tzinfo=None).isoformat()


def unwrap_json_list(raw: str) -> str:
    """
    Convertit '["a", "b"]' en 'a, b', laisse les strings normales intactes.
    Nécessaire car les anciennes démarches DS retournent les valeurs de listes
    déroulantes comme chaînes simples, tandis que les nouvelles les retournent
    sous forme de chaînes JSON encodées.
    """
    if not isinstance(raw, str) or not raw.startswith("["):
        return raw

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw

    if isinstance(parsed, list):
        return ", ".join(str(v) for v in parsed)

    return raw
