from grist.utils import normalize_column_name


class TestNormalizeColumnName:
    """Tests unitaires pour la fonction normalize_column_name"""

    def test_normalize_column_name_basic(self):
        """Test de normalisation basique"""
        assert normalize_column_name("Nom du champ") == "nom_du_champ"
        assert normalize_column_name("Prénom") == "prenom"
        assert normalize_column_name("Email@domain.com") == "email_domain_com"

    def test_normalize_column_name_empty(self):
        """Test avec chaîne vide"""
        assert normalize_column_name("") == "column"
        assert normalize_column_name("   ") == "column"
        assert normalize_column_name("!!!") == "column"
        assert normalize_column_name(None) == "column"

    def test_normalize_column_name_special_chars(self):
        """Test avec caractères spéciaux"""
        assert normalize_column_name("Champ#1!") == "champ_1"
        assert normalize_column_name("Test-Field_123") == "test_field_123"

    def test_normalize_column_name_accents(self):
        """Test avec accents"""
        assert normalize_column_name("Téléphone") == "telephone"
        assert normalize_column_name("Adresse naïve") == "adresse_naive"

    def test_normalize_column_name_multiple_spaces(self):
        """Test avec espaces multiples"""
        assert normalize_column_name("Champ   avec   espaces") == "champ_avec_espaces"

    def test_normalize_column_name_underscores(self):
        """Test avec underscores multiples"""
        assert (
            normalize_column_name("champ__avec__underscores")
            == "champ_avec_underscores"
        )

    def test_normalize_column_name_starts_with_number(self):
        """Test qui commence par un chiffre"""
        assert normalize_column_name("123champ") == "col_123champ"

    def test_normalize_column_name_max_length(self):
        """Test de longueur maximale"""
        long_name = "a" * 60
        result = normalize_column_name(long_name, max_length=50)
        assert len(result) <= 50
        # Function adds hash suffix when truncating: name[:43] + "_" + hash[:6]
        assert result.startswith("a" * 43 + "_")
        assert len(result) == 50

    def test_normalize_column_name_edge_cases(self):
        """Test de cas limites"""
        assert normalize_column_name("_underscore") == "underscore"
        assert normalize_column_name("underscore_") == "underscore"
        assert normalize_column_name("___multiple___") == "multiple"

    def test_normalize_column_name_none(self):
        """None -> nom par défaut"""
        assert normalize_column_name(None) == "column"

    def test_normalize_column_name_apostrophes(self):
        """Les apostrophes séparent les mots"""
        assert normalize_column_name("Nom de l'élève") == "nom_de_l_eleve"
        assert normalize_column_name("l’enseignant") == "l_enseignant"
        assert normalize_column_name("l`enseignant") == "l_enseignant"

    def test_normalize_column_name_strips_leading_numbering(self):
        """La numérotation en tête de libellé est retirée"""
        assert normalize_column_name("1. Nom de l'élève") == "nom_de_l_eleve"
        assert normalize_column_name("2) Date") == "date"
        assert normalize_column_name("3.Adresse") == "adresse"
        assert normalize_column_name("12. Bloc") == "bloc"

    def test_normalize_column_name_keeps_number_without_separator(self):
        """Un nombre sans point ni parenthèse fait partie du libellé"""
        assert normalize_column_name("12 mois") == "col_12_mois"
        assert normalize_column_name("Étape 1. Dépôt") == "etape_1_depot"

    def test_normalize_column_name_max_length_is_stable(self):
        """La troncature est déterministe et distingue deux libellés proches"""
        a = normalize_column_name("x" * 200 + "a")
        b = normalize_column_name("x" * 200 + "b")
        assert len(a) == 150
        assert a == normalize_column_name("x" * 200 + "a")
        assert a != b
