from utils.log_progress import LogProgress, PROGRESS_START


class TestLogProgressInit:
    """Tests d'initialisation de LogProgress"""

    def test_default_values(self):
        """Valeurs par défaut"""
        lp = LogProgress()
        assert lp.ceiling == 5
        assert lp.increment == 0.1
        assert lp.start == PROGRESS_START
        assert PROGRESS_START == 2
        assert lp._value == PROGRESS_START

    def test_custom_values(self):
        """Valeurs personnalisées respectées"""
        lp = LogProgress(ceiling=10, increment=0.5, start=3)
        assert lp.ceiling == 10
        assert lp.increment == 0.5
        assert lp.start == 3
        assert lp._value == 3


class TestLogProgressLog:
    """Tests de la méthode log"""

    def test_increments_value(self):
        """log incrémente _value de increment"""
        lp = LogProgress(ceiling=5, increment=1, start=2)
        lp.log("phase")
        assert lp._value == 3

    def test_reset_flag(self):
        """log(reset=True) réinitialise puis incrémente"""
        lp = LogProgress(ceiling=5, increment=1, start=2)
        lp.log("a")
        lp.log("b", reset=True)
        assert lp._value == 3

    def test_capped_at_ceiling(self):
        """_value ne dépasse jamais ceiling"""
        lp = LogProgress(ceiling=5, increment=10, start=2)
        lp.log("phase")
        assert lp._value == 5

    def test_prints_message(self, capsys):
        """Affiche 'Progression: <valeur> - <phase>...'"""
        lp = LogProgress(ceiling=5, increment=1, start=2)
        lp.log("Traitement")
        captured = capsys.readouterr()
        assert captured.out == "Progression: 3 - Traitement...\n"


class TestLogProgressReset:
    """Tests de la méthode reset"""

    def test_reset_sets_value_to_start(self):
        """reset remet _value à start"""
        lp = LogProgress(ceiling=5, increment=1, start=2)
        lp.log("a")
        lp.reset()
        assert lp._value == 2
