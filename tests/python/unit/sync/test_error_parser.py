import pytest
from unittest.mock import MagicMock
import subprocess
from sync.error_parser import (
    error_message,
    extract_error_parts,
    stderr_error_messages,
)


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

    def test_python_traceback_stderr_is_filtered(self):
        """Le stderr d'un traceback Python se réduit à son message d'exception"""
        e = MagicMock(spec=subprocess.CalledProcessError)
        e.stderr = (
            "Traceback (most recent call last):\n"
            '  File "/app/grist_processor_working_all.py", line 1600, in main\n'
            "    process_demarche(demarche)\n"
            '  File "/app/grist_processor_working_all.py", line 42, in run\n'
            "    raise GristReadError(detail)\n"
            "GristReadError: Grist a refusé l'écriture (403)\n"
        )

        result = extract_error_parts(e, [])

        assert result == ["GristReadError: Grist a refusé l'écriture (403)"]


class TestErrorMessage:
    def test_ligne_erreur_renvoie_le_message_sans_prefixe(self):
        """Ligne ERREUR: → message sans le préfixe ni les espaces qui le suivent"""
        assert error_message("ERREUR:  Connexion échouée") == "Connexion échouée"

    def test_casse_ignoree(self):
        """Erreur: et erreur: sont aussi des lignes d'erreur"""
        assert error_message("Erreur: capitalisé") == "capitalisé"
        assert error_message("erreur: minuscule") == "minuscule"

    def test_ligne_ordinaire_renvoie_none(self):
        """Une ligne sans ERREUR: n'est pas une erreur"""
        assert error_message("Progression: 50 - Traitement") is None
        assert error_message("Dossiers en échec: 11") is None


class TestStderrErrorMessages:
    def test_lignes_vides_ecartees(self):
        """Chaque ligne non vide du stderr est un message"""
        assert stderr_error_messages("Erreur 1\n\n  \nErreur 2\n") == [
            "Erreur 1",
            "Erreur 2",
        ]

    def test_traceback_reduit_au_message_final(self):
        """Les en-têtes et frames d'un traceback Python sont écartés"""
        stderr = (
            "Traceback (most recent call last):\n"
            '  File "/app/grist_processor_working_all.py", line 42, in run\n'
            "    raise GristReadError(detail)\n"
            "GristReadError: Grist a refusé l'écriture (403)\n"
        )

        assert stderr_error_messages(stderr) == [
            "GristReadError: Grist a refusé l'écriture (403)"
        ]

    def test_stderr_vide(self):
        """Stderr vide → aucun message"""
        assert stderr_error_messages("") == []
