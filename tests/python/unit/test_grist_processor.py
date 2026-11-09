from unittest.mock import MagicMock, patch

import pytest

from grist.client import GristReadError
import grist_processor_working_all as gpa
from grist_processor_working_all import (
    add_id_columns_based_on_annotations,
    upsert_avis_records,
)


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

    def test_get_http_error_raises_without_writing(self):
        """GET en échec -> GristReadError, aucun avis recréé en doublon"""
        self.client.get_records.return_value.status_code = 500
        self.client.get_records.return_value.text = "boom"
        avis = [{"avis_id": 1}]

        with pytest.raises(GristReadError):
            upsert_avis_records(self.client, self.TABLE_ID, avis)

        self.client.post_records.assert_not_called()
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


class TestMainGristReadError:
    """Tests unitaires de main() quand une lecture Grist échoue"""

    def _response(self):
        response = MagicMock()
        response.status_code = 400
        response.json.return_value = {"error": "[Sandbox] MemoryError"}
        return response

    def test_returns_dedicated_exit_code_and_user_message(self, monkeypatch, capsys):
        """GristReadError -> code EXIT_CODE_GRIST_READ_ERROR, une seule ligne
        d'erreur explicite, aucune trace d'appels"""
        from utils.constants import EXIT_CODE_GRIST_READ_ERROR

        monkeypatch.setenv("DEMARCHES_API_TOKEN", "token")
        monkeypatch.setenv("DEMARCHE_NUMBER", "128651")
        monkeypatch.setenv("GRIST_BASE_URL", "https://grist.example.com")
        monkeypatch.setenv("GRIST_API_KEY", "key-123456789")
        monkeypatch.setenv("GRIST_DOC_ID", "doc123")
        error = GristReadError("Demarche_128651_dossiers", self._response())

        with patch.object(
            gpa, "verify_api_connections", return_value=(True, [])
        ), patch.object(
            gpa, "process_demarche_for_grist_optimized", side_effect=error
        ):
            exit_code = gpa.main()

        captured = capsys.readouterr()
        assert exit_code == EXIT_CODE_GRIST_READ_ERROR
        error_lines = [
            line for line in captured.out.splitlines() if line.startswith("ERREUR:")
        ]
        assert error_lines == [
            "ERREUR: Grist n'a pas pu lire la table Demarche_128651_dossiers "
            "(400 : [Sandbox] MemoryError). Synchronisation interrompue pour ne "
            "pas créer de doublons ; elle reprendra au prochain lancement."
        ]
        assert "Traceback" not in captured.err
