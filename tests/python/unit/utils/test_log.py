import utils.log
from utils.log import format_numbers, log, log_verbose, log_error, log_sync_errors


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


class TestLogSyncErrors:
    """Tests unitaires pour log_sync_errors"""

    @staticmethod
    def _errors(count: int) -> list[dict[str, str]]:
        return [
            {"timestamp": f"2026-11-16T23:05:{second:02d}.000Z", "message": f"erreur {second}"}
            for second in range(count)
        ]

    def test_en_tete_puis_erreurs_horodatees_dans_l_ordre(self, capsys):
        log_sync_errors("Synchro auto en échec", self._errors(2))

        assert capsys.readouterr().out.splitlines() == [
            "ERREUR: Synchro auto en échec",
            "ERREUR:   2026-11-16T23:05:00.000Z erreur 0",
            "ERREUR:   2026-11-16T23:05:01.000Z erreur 1",
        ]

    def test_sans_erreur_seul_l_en_tete(self, capsys):
        log_sync_errors("Synchro auto en échec", [])

        assert capsys.readouterr().out.splitlines() == ["ERREUR: Synchro auto en échec"]

    def test_a_la_limite_non_tronque(self, capsys):
        log_sync_errors("En-tête", self._errors(3), limit=3)

        lines = capsys.readouterr().out.splitlines()
        assert len(lines) == 4
        assert lines[-1].endswith("erreur 2")

    def test_au_dela_de_la_limite_premieres_gardees_et_reste_compte(self, capsys):
        log_sync_errors("En-tête", self._errors(5), limit=3)

        lines = capsys.readouterr().out.splitlines()
        assert lines[1:4] == [
            f"ERREUR:   2026-11-16T23:05:0{second}.000Z erreur {second}"
            for second in range(3)
        ]
        assert lines[-1] == "ERREUR:   … (+2)"

    def test_limite_par_defaut_20(self, capsys):
        log_sync_errors("En-tête", self._errors(25))

        lines = capsys.readouterr().out.splitlines()
        assert len(lines) == 1 + 20 + 1
        assert lines[-1] == "ERREUR:   … (+5)"
