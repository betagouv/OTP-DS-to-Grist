import utils.log
from utils.log import log, log_verbose, log_error


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
