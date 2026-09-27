from unittest.mock import patch

import pytest

from grist.formatter import format_value

CTX = {"dossier_number": 1, "champ_label": "test"}


class TestFormatValue:
    """Tests unitaires pour la fonction format_value"""

    def test_format_value_none(self):
        """Test avec valeur None"""
        assert format_value(None, "Text", **CTX) is None
        assert format_value(None, "Int", **CTX) is None

    def test_format_value_datetime(self):
        """Test avec type DateTime"""
        # Test avec différents formats de date
        assert (
            format_value("2023-12-25T10:30:00Z", "DateTime", **CTX)
            == "2023-12-25T10:30:00Z"
        )
        assert (
            format_value("2023-12-25T10:30:00.123456Z", "DateTime", **CTX)
            == "2023-12-25T10:30:00Z"
        )
        assert (
            format_value("2023-12-25 10:30:00", "DateTime", **CTX)
            == "2023-12-25T10:30:00Z"
        )
        assert (
            format_value("2023-12-25", "DateTime", **CTX) == "2023-12-25T00:00:00Z"
        )
        # Test avec chaîne invalide
        assert format_value("invalid-date", "DateTime", **CTX) == "invalid-date"

    def test_format_value_text(self):
        """Test avec type Text"""
        # Texte normal
        assert format_value("Hello World", "Text", **CTX) == "Hello World"
        # Texte long (non tronqué)
        long_text = "a" * 1010
        result = format_value(long_text, "Text", **CTX)
        assert isinstance(result, str)
        assert result == long_text
        assert len(result) == 1010
        # Valeur non-string
        assert format_value(123, "Text", **CTX) == "123"

    def test_format_value_int(self):
        """Test avec type Int"""
        assert format_value(42, "Int", **CTX) == 42
        assert format_value("42", "Int", **CTX) == 42
        assert format_value(42.7, "Int", **CTX) == 42  # Tronqué
        assert format_value("42.7", "Int", **CTX) == 42
        assert format_value("", "Int", **CTX) is None
        assert format_value("invalid", "Int", **CTX) is None

    def test_format_value_numeric(self):
        """Test avec type Numeric"""
        assert format_value(42.5, "Numeric", **CTX) == 42.5
        assert format_value("42.5", "Numeric", **CTX) == 42.5
        assert format_value(42, "Numeric", **CTX) == 42.0
        assert format_value("", "Numeric", **CTX) is None
        assert format_value("invalid", "Numeric", **CTX) is None

    def test_format_value_bool(self):
        """Test avec type Bool"""
        # Booléens
        assert format_value(True, "Bool", **CTX) is True
        assert format_value(False, "Bool", **CTX) is False
        # Chaînes
        assert format_value("true", "Bool", **CTX) is True
        assert format_value("1", "Bool", **CTX) is True
        assert format_value("yes", "Bool", **CTX) is True
        assert format_value("oui", "Bool", **CTX) is True
        assert format_value("vrai", "Bool", **CTX) is True
        assert format_value("false", "Bool", **CTX) is False
        assert format_value("0", "Bool", **CTX) is False
        assert format_value("no", "Bool", **CTX) is False
        # Autres valeurs
        assert format_value(1, "Bool", **CTX) is True
        assert format_value(0, "Bool", **CTX) is False
        assert format_value("other", "Bool", **CTX) is False

    def test_format_value_unknown_type(self):
        """Test avec type inconnu"""
        assert format_value("value", "Unknown", **CTX) == "value"
        assert format_value(123, "Unknown", **CTX) == 123

    def test_unconvertible_int_is_logged_with_dossier(self):
        """Une valeur illisible en Int est écrite vide, mais le log nomme le dossier"""
        with patch("grist.formatter.log_error") as mock_log_error:
            assert (
                format_value(
                    "n/a", "Int", dossier_number=12345, champ_label="quantite"
                )
                is None
            )
        message = mock_log_error.call_args[0][0]
        assert "dossier 12345" in message
        assert "quantite" in message
        assert "n/a" in message

    def test_unparseable_date_is_logged_with_dossier(self):
        """Une date non reconnue part telle quelle, mais le log nomme le dossier"""
        with patch("grist.formatter.log_error") as mock_log_error:
            assert (
                format_value(
                    "hier", "DateTime", dossier_number=12345, champ_label="date_depot"
                )
                == "hier"
            )
        message = mock_log_error.call_args[0][0]
        assert "dossier 12345" in message
        assert "date_depot" in message

    def test_valid_values_are_not_logged(self):
        """Une conversion réussie ne produit aucun log d'erreur"""
        with patch("grist.formatter.log_error") as mock_log_error:
            format_value("42", "Int", **CTX)
            format_value("2023-12-25", "DateTime", **CTX)
            format_value("texte", "Text", **CTX)
            format_value(None, "Int", **CTX)
        mock_log_error.assert_not_called()

    def test_logged_value_is_truncated(self):
        """Une valeur aberrante trop longue est tronquée dans le log"""
        valeur = "n/" + "a" * 200
        with patch("grist.formatter.log_error") as mock_log_error:
            assert (
                format_value(
                    valeur, "Int", dossier_number=42, champ_label="quantite"
                )
                is None
            )
        message = mock_log_error.call_args[0][0]
        assert valeur[:80] in message
        assert valeur[:81] not in message

    def test_dossier_context_is_required(self):
        """Le numéro de dossier et le libellé du champ sont obligatoires : sans eux,
        impossible de rattacher une valeur abandonnée à un dossier"""
        with pytest.raises(TypeError):
            format_value("42", "Int")
        with pytest.raises(TypeError):
            format_value("42", "Int", dossier_number=1)
        with pytest.raises(TypeError):
            format_value("42", "Int", champ_label="quantite")
