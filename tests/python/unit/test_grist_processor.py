from unittest.mock import MagicMock

from grist_processor_working_all import (
    normalize_column_name,
    format_value_for_grist,
    filter_record_to_existing_columns,
    add_id_columns_based_on_annotations,
    upsert_avis_records,
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


class TestFilterRecordToExistingColumns:
    """Tests unitaires pour filter_record_to_existing_columns"""

    def setup_method(self):
        self.client = MagicMock()

    def test_filters_unknown_columns(self):
        """ne garde que les colonnes existantes"""
        self.client.get_columns.return_value = {"name": "Text", "email": "Text"}
        result = filter_record_to_existing_columns(
            self.client, "dossiers", {"name": "x", "toto": 1}
        )
        assert result == {"name": "x"}

    def test_keeps_dossier_number_even_if_absent(self):
        """dossier_number est toujours conservé même s'il n'existe pas dans la table"""
        self.client.get_columns.return_value = {"name": "Text"}
        result = filter_record_to_existing_columns(
            self.client, "dossiers", {"name": "x", "dossier_number": 5}
        )
        assert result == {"name": "x", "dossier_number": 5}

    def test_returns_record_unchanged_on_http_error(self):
        """erreur HTTP -> enregistrement inchangé"""
        self.client.get_columns.return_value = {}
        result = filter_record_to_existing_columns(
            self.client, "dossiers", {"name": "x", "toto": 1}
        )
        assert result == {"name": "x", "toto": 1}

    def test_returns_record_unchanged_on_exception(self):
        """exception -> enregistrement inchangé"""
        self.client.get_columns.side_effect = Exception("boom")
        result = filter_record_to_existing_columns(
            self.client, "dossiers", {"name": "x"}
        )
        assert result == {"name": "x"}


class TestAddIdColumnsBasedOnAnnotations:
    """Tests unitaires pour add_id_columns_based_on_annotations"""

    def setup_method(self):
        self.client = MagicMock()

    def _mock_post(self, status=200):
        response = MagicMock()
        response.status_code = status
        response.text = "err"
        return response

    def test_creates_only_missing_id_columns(self):
        """ne crée que les colonnes *_id manquantes"""
        self.client.get_columns.return_value = {"commentaire_id": "Text"}
        self.client.add_columns.return_value = self._mock_post()
        annotations = [
            {"id": 1, "label": "Commentaire"},
            {"id": 2, "label": "annotation_Réponse"},
        ]
        result = add_id_columns_based_on_annotations(
            self.client, "annotations", annotations
        )
        assert result == ["reponse_id"]
        self.client.add_columns.assert_called_once()
        assert self.client.add_columns.call_args.args[0] == "annotations"
        assert self.client.add_columns.call_args.args[1] == [
            {"id": "reponse_id", "type": "Text"}
        ]

    def test_posts_all_when_get_fails(self):
        """GET en échec -> aucun filtrage, POST de toutes les colonnes"""
        self.client.get_columns.return_value = {}
        self.client.add_columns.return_value = self._mock_post()
        annotations = [{"id": 1, "label": "Commentaire"}]
        result = add_id_columns_based_on_annotations(
            self.client, "annotations", annotations
        )
        assert result == ["commentaire_id"]
        self.client.add_columns.assert_called_once()
        assert self.client.add_columns.call_args.args[0] == "annotations"
        assert self.client.add_columns.call_args.args[1] == [
            {"id": "commentaire_id", "type": "Text"}
        ]

    def test_skips_annotations_without_label_or_id(self):
        """annotation sans label ou sans id -> ignorée"""
        self.client.get_columns.return_value = {}
        self.client.add_columns.return_value = self._mock_post()
        annotations = [
            {"id": 1, "label": "Commentaire"},
            {"label": "Sans id"},
            {"id": 2},
        ]
        result = add_id_columns_based_on_annotations(
            self.client, "annotations", annotations
        )
        assert result == ["commentaire_id"]
        assert len(self.client.add_columns.call_args.args[1]) == 1

    def test_no_post_when_all_columns_exist(self):
        """toutes les colonnes existent -> pas de POST, retour None"""
        self.client.get_columns.return_value = {"commentaire_id": "Text"}
        annotations = [{"id": 1, "label": "Commentaire"}]
        result = add_id_columns_based_on_annotations(
            self.client, "annotations", annotations
        )
        assert result is None
        self.client.add_columns.assert_not_called()

    def test_no_annotations_no_http(self):
        """aucune annotation -> aucun appel HTTP"""
        result = add_id_columns_based_on_annotations(
            self.client, "annotations", []
        )
        assert result is None
        self.client.add_columns.assert_not_called()
        self.client.get_columns.assert_not_called()


class TestUpsertAvisRecords:
    """Tests unitaires pour upsert_avis_records"""

    TABLE_ID = "Demarche_123_avis"

    def setup_method(self):
        self.client = MagicMock()
        self.client.get_records.return_value.status_code = 200
        self.client.get_records.return_value.json.return_value = {"records": []}
        self.client.post_records.return_value.status_code = 201
        self.client.patch_records.return_value.status_code = 200

    def _mock_existing(self, existing_records):
        self.client.get_records.return_value.status_code = 200
        self.client.get_records.return_value.json.return_value = {
            "records": existing_records
        }

    def test_creates_and_updates_by_avis_id(self):
        """upsert : existants mis à jour, nouveaux créés, indexé par avis_id"""
        existing = [
            {"id": 100, "fields": {"avis_id": 10}},
            {"id": 200, "fields": {"avis_id": 20}},
        ]
        self._mock_existing(existing)

        avis_10 = {"avis_id": 10, "title": "A"}
        avis_30 = {"avis_id": 30, "title": "B"}
        avis_20 = {"avis_id": 20, "title": "C"}

        nb_created, nb_updated = upsert_avis_records(
            self.client, self.TABLE_ID, [avis_10, avis_30, avis_20]
        )

        assert (nb_created, nb_updated) == (1, 2)
        self.client.get_records.assert_called_once_with(self.TABLE_ID)
        self.client.post_records.assert_called_once_with(
            self.TABLE_ID, [{"fields": avis_30}]
        )
        self.client.patch_records.assert_called_once_with(
            self.TABLE_ID,
            [
                {"id": 100, "fields": avis_10},
                {"id": 200, "fields": avis_20},
            ],
        )

    def test_creates_all_when_no_existing(self):
        """aucun existant -> tout en création, pas de PATCH"""
        avis = [{"avis_id": 1}, {"avis_id": 2}]

        nb_created, nb_updated = upsert_avis_records(
            self.client, self.TABLE_ID, avis
        )

        assert (nb_created, nb_updated) == (2, 0)
        self.client.post_records.assert_called_once()
        self.client.patch_records.assert_not_called()

    def test_updates_all_when_all_exist(self):
        """tout existant -> pas de POST, PATCH uniquement"""
        existing = [
            {"id": 100, "fields": {"avis_id": 1}},
            {"id": 200, "fields": {"avis_id": 2}},
        ]
        self._mock_existing(existing)
        avis = [{"avis_id": 1}, {"avis_id": 2}]

        nb_created, nb_updated = upsert_avis_records(
            self.client, self.TABLE_ID, avis
        )

        assert (nb_created, nb_updated) == (0, 2)
        self.client.post_records.assert_not_called()
        self.client.patch_records.assert_called_once()

    def test_get_http_error_creates_all(self):
        """GET en échec -> aucun existant indexé, tout créé, pas d'erreur levée"""
        self.client.get_records.return_value.status_code = 500
        avis = [{"avis_id": 1}]

        nb_created, nb_updated = upsert_avis_records(
            self.client, self.TABLE_ID, avis
        )

        assert (nb_created, nb_updated) == (1, 0)
        self.client.post_records.assert_called_once()
        self.client.patch_records.assert_not_called()

    def test_avis_without_avis_id_are_created(self):
        """un avis sans avis_id (entrant) est créé ; un existant sans avis_id n'est pas indexé"""
        existing = [
            {"id": 100, "fields": {"title": "sans id"}},
            {"id": 200, "fields": {"avis_id": 5}},
        ]
        self._mock_existing(existing)
        sans_id = {"title": "nouveau sans id"}
        avis_5 = {"avis_id": 5}

        nb_created, nb_updated = upsert_avis_records(
            self.client, self.TABLE_ID, [sans_id, avis_5]
        )

        assert (nb_created, nb_updated) == (1, 1)
        self.client.post_records.assert_called_once_with(
            self.TABLE_ID, [{"fields": sans_id}]
        )
        self.client.patch_records.assert_called_once_with(
            self.TABLE_ID, [{"id": 200, "fields": avis_5}]
        )

    def test_empty_avis_no_post_no_patch(self):
        """aucun avis -> GET quand même, pas de POST ni PATCH"""
        nb_created, nb_updated = upsert_avis_records(self.client, self.TABLE_ID, [])

        assert (nb_created, nb_updated) == (0, 0)
        self.client.get_records.assert_called_once()
        self.client.post_records.assert_not_called()
        self.client.patch_records.assert_not_called()
