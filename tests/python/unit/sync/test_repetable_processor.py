"""
Tests unitaires pour sync/repetable_processor.py : normalize_column_name

Cette copie de normalize_column_name NE stripe PAS les numéros en début.
Elle est identique à label_to_column_id (common/formatter.py).
"""

from sync.repetable_processor import normalize_column_name


class TestNormalizeColumnName:
    """Tests pour normalize_column_name de sync/repetable_processor."""

    def test_basic(self):
        assert normalize_column_name("Nom du champ") == "nom_du_champ"
        assert normalize_column_name("Prénom") == "prenom"
        assert normalize_column_name("Email@domain.com") == "email_domain_com"

    def test_empty_and_whitespace(self):
        assert normalize_column_name("") == "column"
        assert normalize_column_name("   ") == "col_"

    def test_accents(self):
        assert normalize_column_name("Téléphone") == "telephone"
        assert normalize_column_name("Adresse naïve") == "adresse_naive"

    def test_apostrophes(self):
        assert normalize_column_name("l'enseignant") == "l_enseignant"

    def test_special_characters(self):
        assert normalize_column_name("Champ#1!") == "champ_1"
        assert normalize_column_name("Test-Field_123") == "test_field_123"

    def test_starts_with_number(self):
        assert normalize_column_name("123champ") == "col_123champ"

    def test_no_strip_numbered_label(self):
        """Pas de stripping des numéros en début — comportement de cette copie."""
        assert normalize_column_name("1. Nom du champ") == "col_1_nom_du_champ"
        assert normalize_column_name("2) Prénom") == "col_2_prenom"
        assert normalize_column_name("3. Documents") == "col_3_documents"

    def test_max_length(self):
        long_name = "a" * 60
        result = normalize_column_name(long_name, max_length=50)
        assert len(result) <= 50

    def test_underscores(self):
        assert normalize_column_name("champ__avec__underscores") == "champ_avec_underscores"
        assert normalize_column_name("_underscore") == "underscore"
        assert normalize_column_name("___multiple___") == "multiple"
