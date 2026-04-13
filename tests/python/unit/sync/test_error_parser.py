import pytest
from unittest.mock import MagicMock
import subprocess
from sync.error_parser import extract_error_parts


class TestExtractErrorParts:
    def test_stderr_extraction(self):
        """Erreurs extraites depuis stderr"""
        e = MagicMock(spec=subprocess.CalledProcessError)
        e.stderr = "Erreur de connexion\nToken invalide"

        output_lines = []
        result = extract_error_parts(e, output_lines)

        assert len(result) == 2
        assert "Erreur de connexion" in result
        assert "Token invalide" in result

    def test_stdout_erreur_extraction(self):
        """Lignes ERREUR: extraites depuis stdout"""
        e = MagicMock()
        e.stderr = None

        output_lines = [
            "Progression: 50 - Traitement",
            "ERREUR: Token invalide",
            "ERREUR:  Connexion échouée",
        ]
        result = extract_error_parts(e, output_lines)

        assert len(result) == 2
        assert "Token invalide" in result
        assert "Connexion échouée" in result

    def test_combined_stderr_stdout(self):
        """Combinaison stderr + stdout"""
        e = MagicMock(spec=subprocess.CalledProcessError)
        e.stderr = "Erreur système"

        output_lines = ["ERREUR: Token expiré"]
        result = extract_error_parts(e, output_lines)

        assert len(result) == 2
        assert "Erreur système" in result
        assert "Token expiré" in result

    def test_case_insensitive(self):
        """ERREUR:, Erreur:, erreur: tous capturés"""
        e = MagicMock()
        e.stderr = None

        output_lines = [
            "ERREUR: Erreur majuscules",
            "Erreur: Erreur capitalisé",
            "erreur: Erreur minuscule",
        ]
        result = extract_error_parts(e, output_lines)

        assert len(result) == 3
        assert "Erreur majuscules" in result
        assert "Erreur capitalisé" in result
        assert "Erreur minuscule" in result

    def test_empty_returns_empty_list(self):
        """Pas d'erreurs → liste vide"""
        e = MagicMock()
        e.stderr = None

        output_lines = ["Progression: 50", "Synchronisation terminée"]
        result = extract_error_parts(e, output_lines)

        assert result == []

    def test_prefix_removed(self):
        """Préfixe ERREUR: retiré du message"""
        e = MagicMock()
        e.stderr = None

        output_lines = ["ERREUR: Message d'erreur"]
        result = extract_error_parts(e, output_lines)

        assert result[0] == "Message d'erreur"
        assert "ERREUR:" not in result[0]

    def test_empty_lines_ignored(self):
        """Lignes vides ignorées"""
        e = MagicMock(spec=subprocess.CalledProcessError)
        e.stderr = "Erreur 1\n\nErreur 2\n\n"

        output_lines = ["ERREUR: Erreur 3", "", "ERREUR: Erreur 4"]
        result = extract_error_parts(e, output_lines)

        assert len(result) == 4
        assert "" not in result
