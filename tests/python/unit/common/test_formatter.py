"""
Tests unitaires pour common/formatter.py : label_to_column_id
"""

from common.formatter import label_to_column_id


class TestLabelToColumnId:
    """Tests pour label_to_column_id"""

    def test_basic_labels(self):
        assert label_to_column_id("Nom du champ") == "nom_du_champ"
        assert label_to_column_id("Prénom") == "prenom"
        assert label_to_column_id("Email@domain.com") == "email_domain_com"

    def test_empty_and_whitespace(self):
        assert label_to_column_id("") == "column"
        assert label_to_column_id("   ") == "col_"
        assert label_to_column_id(None) == "column"

    def test_special_characters(self):
        assert label_to_column_id("Champ#1!") == "champ_1"
        assert label_to_column_id("Test-Field_123") == "test_field_123"

    def test_accents(self):
        assert label_to_column_id("Téléphone") == "telephone"
        assert label_to_column_id("Adresse naïve") == "adresse_naive"

    def test_multiple_spaces(self):
        assert label_to_column_id("Champ   avec   espaces") == "champ_avec_espaces"

    def test_multiple_underscores(self):
        assert label_to_column_id("champ__avec__underscores") == "champ_avec_underscores"

    def test_starts_with_number(self):
        assert label_to_column_id("123champ") == "col_123champ"

    def test_max_length(self):
        long_name = "a" * 60
        result = label_to_column_id(long_name, max_length=50)
        assert len(result) <= 50
        assert result.startswith("a" * 43 + "_")
        assert len(result) == 50

    def test_edge_cases(self):
        assert label_to_column_id("_underscore") == "underscore"
        assert label_to_column_id("underscore_") == "underscore"
        assert label_to_column_id("___multiple___") == "multiple"

    def test_apostrophes(self):
        assert label_to_column_id("l'enseignant") == "l_enseignant"
        assert label_to_column_id("l\u2019enseignant") == "l_enseignant"
        assert label_to_column_id("l`enseignant") == "l_enseignant"

    def test_no_leading_number_stripping(self):
        """Vérifie que label_to_column_id NE supprime PAS les numéros en début (col_ préfixé)."""
        assert label_to_column_id("1. Nom du champ") == "col_1_nom_du_champ"
        assert label_to_column_id("2) Prénom") == "col_2_prenom"
        assert label_to_column_id("3) Documents") == "col_3_documents"
        assert label_to_column_id("12. Adresse complète") == "col_12_adresse_complete"
        assert label_to_column_id("1er étage") == "col_1er_etage"

    def test_returns_string(self):
        assert isinstance(label_to_column_id("test"), str)
