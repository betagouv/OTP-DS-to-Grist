import time

from utils.timing import clear_timings, get_timings, timed


def test_timed_enregistre_un_timing():
    clear_timings()

    @timed("ma_fonction", "test")
    def ma_fonction():
        return 42

    assert ma_fonction() == 42

    timings = get_timings()
    assert len(timings) == 1
    assert timings[0]["service"] == "test"
    assert timings[0]["function"] == "ma_fonction"
    assert timings[0]["duration"] >= 0


def test_timed_capture_arguments():
    clear_timings()

    @timed("ma_fonction")
    def ma_fonction(a, b=2):
        return a + b

    ma_fonction(1, b=3)

    timings = get_timings()
    assert timings[0]["args"] == (1,)
    assert timings[0]["kwargs"] == {"b": 3}


def test_timed_avec_duree_mesuree():
    clear_timings()

    @timed("lente", "test")
    def lente():
        time.sleep(0.01)

    lente()

    timings = get_timings()
    assert timings[0]["duration"] >= 0.01


def test_get_timings_retourne_une_copie():
    clear_timings()

    @timed("fonction", "test")
    def fonction():
        pass

    fonction()

    timings = get_timings()
    timings.clear()

    assert len(get_timings()) == 1


def test_clear_timings_vide_la_liste():
    clear_timings()

    @timed("fonction", "test")
    def fonction():
        pass

    fonction()
    clear_timings()

    assert get_timings() == []