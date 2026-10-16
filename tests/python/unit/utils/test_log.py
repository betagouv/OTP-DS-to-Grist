import utils.log
from utils.log import format_numbers, log, log_verbose, log_error


class TestLoggingFunctions:
    """Tests unitaires pour les fonctions de logging"""

    def test_log_with_level_1(self, capsys):
        """Test log avec niveau 1 (défaut)"""
        original_level = utils.log.LOG_LEVEL
        utils.log.LOG_LEVEL = 1
        try:
            log("Test message", 1)
            captured = capsys.readouterr()
            assert captured.out.strip() == "Test message"
        finally:
            utils.log.LOG_LEVEL = original_level

    def test_log_with_level_above_threshold(self, capsys):
        """Test log avec niveau supérieur au seuil"""
        original_level = utils.log.LOG_LEVEL
        utils.log.LOG_LEVEL = 1
        try:
            log("Test message", 2)
            captured = capsys.readouterr()
            assert captured.out == ""  # Ne devrait pas afficher
        finally:
            utils.log.LOG_LEVEL = original_level

    def test_log_verbose(self, capsys):
        """Test log_verbose"""
        original_level = utils.log.LOG_LEVEL
        utils.log.LOG_LEVEL = 2
        try:
            log_verbose("Verbose message")
            captured = capsys.readouterr()
            assert captured.out.strip() == "Verbose message"
        finally:
            utils.log.LOG_LEVEL = original_level

    def test_log_error(self, capsys):
        """Test log_error (toujours affiché)"""
        log_error("Error message")
        captured = capsys.readouterr()
        assert captured.out.strip() == "ERREUR: Error message"


class TestFormatNumbers:
    """Tests unitaires pour format_numbers"""

    def test_empty(self):
        assert format_numbers(set()) == ""

    def test_sorted_numerically(self):
        """Tri numérique, pas lexicographique : 9 avant 10 avant 100"""
        assert format_numbers({"100", "10", "9"}) == "9, 10, 100"

    def test_at_limit_not_truncated(self):
        numbers = {str(i) for i in range(1, 4)}
        assert format_numbers(numbers, limit=3) == "1, 2, 3"

    def test_above_limit_truncated_with_remaining_count(self):
        numbers = {str(i) for i in range(1, 6)}
        assert format_numbers(numbers, limit=3) == "1, 2, 3, … (+2)"

    def test_default_limit_is_20(self):
        numbers = {str(i) for i in range(1, 26)}
        assert format_numbers(numbers).endswith("19, 20, … (+5)")
