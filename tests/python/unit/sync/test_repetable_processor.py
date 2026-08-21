"""
Tests unitaires pour sync/repetable_processor.py

Avant 6a.6, sync/repetable_processor.py avait sa propre copie de
label_to_column_id (sans stripping des numéros). Cette copie est
identique à label_to_column_id de common/formatter.py.

Ce fichier teste le comportement de label_to_column_id tel qu'utilisé
dans sync/repetable_processor (sans stripping des numéros).
"""

from common.formatter import label_to_column_id


class TestNormalizeColumnName:
    """Tests pour label_to_column_id de sync/repetable_processor."""

    def test_basic(self):
        assert label_to_column_id("Nom du champ") == "nom_du_champ"
        assert label_to_column_id("Prénom") == "prenom"
        assert label_to_column_id("Email@domain.com") == "email_domain_com"

    def test_empty_and_whitespace(self):
        assert label_to_column_id("") == "column"
        assert label_to_column_id("   ") == "col_"

    def test_accents(self):
        assert label_to_column_id("Téléphone") == "telephone"
        assert label_to_column_id("Adresse naïve") == "adresse_naive"

    def test_apostrophes(self):
        assert label_to_column_id("l'enseignant") == "l_enseignant"

    def test_special_characters(self):
        assert label_to_column_id("Champ#1!") == "champ_1"
        assert label_to_column_id("Test-Field_123") == "test_field_123"

    def test_starts_with_number(self):
        assert label_to_column_id("123champ") == "col_123champ"

    def test_no_strip_numbered_label(self):
        """Pas de stripping des numéros en début — comportement de cette copie."""
        assert label_to_column_id("1. Nom du champ") == "col_1_nom_du_champ"
        assert label_to_column_id("2) Prénom") == "col_2_prenom"
        assert label_to_column_id("3. Documents") == "col_3_documents"

    def test_max_length(self):
        long_name = "a" * 60
        result = label_to_column_id(long_name, max_length=50)
        assert len(result) <= 50

    def test_underscores(self):
        assert label_to_column_id("champ__avec__underscores") == "champ_avec_underscores"
        assert label_to_column_id("_underscore") == "underscore"
        assert label_to_column_id("___multiple___") == "multiple"
