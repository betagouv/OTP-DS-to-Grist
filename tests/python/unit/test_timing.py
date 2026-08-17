from utils.timing import _timings, get_timings, timed


def test_timed_records_duration():
    _timings.clear()

    @timed("test_func", "test_service")
    def dummy():
        return 42

    result = dummy()
    assert result == 42
    assert len(_timings) == 1
    assert _timings[0]["function"] == "test_func"
    assert _timings[0]["service"] == "test_service"
    assert _timings[0]["duration"] >= 0
    _timings.clear()


def test_timed_records_exception():
    _timings.clear()

    @timed("failing_func", "test_service")
    def failing():
        raise ValueError("boom")

    try:
        failing()
    except ValueError:
        pass
    assert len(_timings) == 1
    assert _timings[0]["function"] == "failing_func"
    _timings.clear()


def test_get_timings_returns_copy():
    _timings.clear()
    _timings.append({"function": "manual", "duration": 1.0})
    result = get_timings()
    result.clear()
    assert len(_timings) == 1
    _timings.clear()
