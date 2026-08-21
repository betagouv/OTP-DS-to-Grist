from common.formatter import ds_label_to_column_id
from grist_processor_working_all import (
    format_value_for_grist,
)


class TestDsLabelToColumnId:
    """Tests pour ds_label_to_column_id — remplace l'ancien normalize_column_name."""

    def test_normalize_column_name_basic(self):
        """Test de normalisation basique"""
        assert ds_label_to_column_id("Nom du champ") == "nom_du_champ"
        assert ds_label_to_column_id("Prénom") == "prenom"
        assert ds_label_to_column_id("Email@domain.com") == "email_domain_com"

    def test_normalize_column_name_empty(self):
        """Test avec chaîne vide"""
        assert ds_label_to_column_id("") == "column"
        assert ds_label_to_column_id("   ") == "col_"

    def test_normalize_column_name_special_chars(self):
        """Test avec caractères spéciaux"""
        assert ds_label_to_column_id("Champ#1!") == "champ_1"
        assert ds_label_to_column_id("Test-Field_123") == "test_field_123"

    def test_normalize_column_name_accents(self):
        """Test avec accents"""
        assert ds_label_to_column_id("Téléphone") == "telephone"
        assert ds_label_to_column_id("Adresse naïve") == "adresse_naive"

    def test_normalize_column_name_multiple_spaces(self):
        """Test avec espaces multiples"""
        assert ds_label_to_column_id("Champ   avec   espaces") == "champ_avec_espaces"

    def test_normalize_column_name_underscores(self):
        """Test avec underscores multiples"""
        assert (
            ds_label_to_column_id("champ__avec__underscores")
            == "champ_avec_underscores"
        )

    def test_normalize_column_name_starts_with_number(self):
        """Test qui commence par un chiffre"""
        assert ds_label_to_column_id("123champ") == "col_123champ"

    def test_normalize_column_name_max_length(self):
        """Test de longueur maximale"""
        long_name = "a" * 60
        result = ds_label_to_column_id(long_name, max_length=50)
        assert len(result) <= 50
        # Function adds hash suffix when truncating: name[:43] + "_" + hash[:6]
        assert result.startswith("a" * 43 + "_")
        assert len(result) == 50

    def test_normalize_column_name_edge_cases(self):
        """Test de cas limites"""
        assert ds_label_to_column_id("_underscore") == "underscore"
        assert ds_label_to_column_id("underscore_") == "underscore"
        assert ds_label_to_column_id("___multiple___") == "multiple"

    def test_strips_numbered_labels(self):
        """Les labels numérotés DS sont stripés — comportement identique à l'ancien normalize_column_name."""
        assert ds_label_to_column_id("1. Nom du champ") == "nom_du_champ"
        assert ds_label_to_column_id("2) Prénom") == "prenom"
        assert ds_label_to_column_id("3. Documents") == "documents"
        assert ds_label_to_column_id("12. Adresse complète") == "adresse_complete"


class TestFormatValueForGrist:
    """Tests unitaires pour la fonction format_value_for_grist"""

    def test_format_value_none(self):
        """Test avec valeur None"""
        assert format_value_for_grist(None, "Text") is None
        assert format_value_for_grist(None, "Int") is None

    def test_format_value_datetime(self):
        """Test avec type DateTime"""
        # Test avec différents formats de date
        assert (
            format_value_for_grist("2023-12-25T10:30:00Z", "DateTime")
            == "2023-12-25T10:30:00Z"
        )
        assert (
            format_value_for_grist("2023-12-25T10:30:00.123456Z", "DateTime")
            == "2023-12-25T10:30:00Z"
        )
        assert (
            format_value_for_grist("2023-12-25 10:30:00", "DateTime")
            == "2023-12-25T10:30:00Z"
        )
        assert (
            format_value_for_grist("2023-12-25", "DateTime") == "2023-12-25T00:00:00Z"
        )
        # Test avec chaîne invalide
        assert format_value_for_grist("invalid-date", "DateTime") == "invalid-date"

    def test_format_value_text(self):
        """Test avec type Text"""
        # Texte normal
        assert format_value_for_grist("Hello World", "Text") == "Hello World"
        # Texte long (non tronqué)
        long_text = "a" * 1010
        result = format_value_for_grist(long_text, "Text")
        assert isinstance(result, str)
        assert result == long_text
        assert len(result) == 1010
        # Valeur non-string
        assert format_value_for_grist(123, "Text") == "123"

    def test_format_value_int(self):
        """Test avec type Int"""
        assert format_value_for_grist(42, "Int") == 42
        assert format_value_for_grist("42", "Int") == 42
        assert format_value_for_grist(42.7, "Int") == 42  # Tronqué
        assert format_value_for_grist("42.7", "Int") == 42
        assert format_value_for_grist("", "Int") is None
        assert format_value_for_grist("invalid", "Int") is None

    def test_format_value_numeric(self):
        """Test avec type Numeric"""
        assert format_value_for_grist(42.5, "Numeric") == 42.5
        assert format_value_for_grist("42.5", "Numeric") == 42.5
        assert format_value_for_grist(42, "Numeric") == 42.0
        assert format_value_for_grist("", "Numeric") is None
        assert format_value_for_grist("invalid", "Numeric") is None

    def test_format_value_bool(self):
        """Test avec type Bool"""
        # Booléens
        assert format_value_for_grist(True, "Bool") is True
        assert format_value_for_grist(False, "Bool") is False
        # Chaînes
        assert format_value_for_grist("true", "Bool") is True
        assert format_value_for_grist("1", "Bool") is True
        assert format_value_for_grist("yes", "Bool") is True
        assert format_value_for_grist("oui", "Bool") is True
        assert format_value_for_grist("vrai", "Bool") is True
        assert format_value_for_grist("false", "Bool") is False
        assert format_value_for_grist("0", "Bool") is False
        assert format_value_for_grist("no", "Bool") is False
        # Autres valeurs
        assert format_value_for_grist(1, "Bool") is True
        assert format_value_for_grist(0, "Bool") is False
        assert format_value_for_grist("other", "Bool") is False

    def test_format_value_unknown_type(self):
        """Test avec type inconnu"""
        assert format_value_for_grist("value", "Unknown") == "value"
        assert format_value_for_grist(123, "Unknown") == 123
