from datetime import datetime, timezone


def _convert(value):
    """Réplique la logique inline de grist_processor_working_all.py"""
    if isinstance(value, (int, float)) and value:
        return datetime.fromtimestamp(value, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    return value


def test_cursor_string_reste_inchange():
    assert _convert("2026-04-14T09:22:48Z") == "2026-04-14T09:22:48Z"


def test_cursor_int_converti_en_str():
    result = _convert(1744622568)
    assert isinstance(result, str)
    assert "T" in result
    assert result.endswith("Z")


def test_cursor_none_reste_none():
    assert _convert(None) is None


def test_cursor_zero_reste_zero():
    assert _convert(0) == 0
