from unittest.mock import patch, MagicMock

from grist_processor_working_all import (
    normalize_column_name,
    format_value_for_grist,
    log,
    log_verbose,
    log_error,
    GristClient,
)


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
        assert normalize_column_name("   ") == "col_"

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


class TestLoggingFunctions:
    """Tests unitaires pour les fonctions de logging"""

    def test_log_with_level_1(self, capsys):
        """Test log avec niveau 1 (défaut)"""
        import grist_processor_working_all
        original_level = grist_processor_working_all.LOG_LEVEL
        grist_processor_working_all.LOG_LEVEL = 1
        try:
            log("Test message", 1)
            captured = capsys.readouterr()
            assert captured.out.strip() == "Test message"
        finally:
            grist_processor_working_all.LOG_LEVEL = original_level

    def test_log_with_level_above_threshold(self, capsys):
        """Test log avec niveau supérieur au seuil"""
        import grist_processor_working_all
        original_level = grist_processor_working_all.LOG_LEVEL
        grist_processor_working_all.LOG_LEVEL = 1
        try:
            log("Test message", 2)
            captured = capsys.readouterr()
            assert captured.out == ""  # Ne devrait pas afficher
        finally:
            grist_processor_working_all.LOG_LEVEL = original_level

    def test_log_verbose(self, capsys):
        """Test log_verbose"""
        import grist_processor_working_all
        original_level = grist_processor_working_all.LOG_LEVEL
        grist_processor_working_all.LOG_LEVEL = 2
        try:
            log_verbose("Verbose message")
            captured = capsys.readouterr()
            assert captured.out.strip() == "Verbose message"
        finally:
            grist_processor_working_all.LOG_LEVEL = original_level

    def test_log_error(self, capsys):
        """Test log_error (toujours affiché)"""
        log_error("Error message")
        captured = capsys.readouterr()
        assert captured.out.strip() == "ERREUR: Error message"


class TestExtractEmailFromScim:
    """Tests unitaires pour GristClient._extract_email_from_scim"""

    def setup_method(self):
        self.client = GristClient("https://grist.example.com", "test_key")

    def test_primary_email(self):
        """Retourne l'email marqué primary"""
        data = {
            "emails": [
                {"value": "second@example.com", "primary": False},
                {"value": "primary@example.com", "primary": True},
            ]
        }
        assert self.client._extract_email_from_scim(data) == "primary@example.com"

    def test_no_primary_returns_first(self):
        """Sans primary, retourne le premier email"""
        data = {"emails": [{"value": "first@example.com"}]}
        assert self.client._extract_email_from_scim(data) == "first@example.com"

    def test_empty_emails(self):
        """emails vide -> None"""
        assert self.client._extract_email_from_scim({"emails": []}) is None

    def test_missing_emails(self):
        """emails absent -> None"""
        assert self.client._extract_email_from_scim({}) is None

    def test_user_name_ignored(self):
        """userName seul (sans emails) est ignoré -> None"""
        data = {"userName": "john.doe@example.com"}
        assert self.client._extract_email_from_scim(data) is None


class TestGetGristUserEmail:
    """Tests unitaires pour GristClient.get_grist_user_email"""

    def setup_method(self):
        self.client = GristClient("https://grist.example.com", "test_key")

    def test_success_primary_email(self):
        """200 avec primary -> retourne l'email"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "emails": [
                {"value": "primary@example.com", "primary": True},
            ]
        }
        with patch(
            "grist_processor_working_all.requests.get",
            return_value=mock_response,
        ):
            assert self.client.get_grist_user_email() == "primary@example.com"

    def test_success_no_primary(self):
        """200 sans primary -> retourne le premier email"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"emails": [{"value": "first@example.com"}]}
        with patch(
            "grist_processor_working_all.requests.get",
            return_value=mock_response,
        ):
            assert self.client.get_grist_user_email() == "first@example.com"

    def test_http_error_returns_none(self):
        """401 -> None"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        with patch(
            "grist_processor_working_all.requests.get",
            return_value=mock_response,
        ):
            assert self.client.get_grist_user_email() is None

    def test_timeout_returns_none(self):
        """Timeout -> None"""
        with patch(
            "grist_processor_working_all.requests.get",
            side_effect=Exception("timeout"),
        ):
            assert self.client.get_grist_user_email() is None

    def test_success_no_emails(self):
        """200 sans emails[] -> None"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"userName": "john.doe@example.com"}
        with patch(
            "grist_processor_working_all.requests.get",
            return_value=mock_response,
        ):
            assert self.client.get_grist_user_email() is None
