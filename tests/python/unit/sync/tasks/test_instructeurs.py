"""
Tests unitaires pour la tâche de synchronisation des instructeurs

Ces tests couvrent :
- La construction de la clé composite instructeur / groupe
- L'indexation des enregistrements Grist existants
- Le calcul des créations, mises à jour et suppressions
- La lecture de la table Grist et son comportement en erreur
- L'orchestration complète de sync_instructeurs
"""

from unittest.mock import MagicMock, patch

import pytest

from sync.tasks.instructeurs import (
    _apply_records_diff,
    _build_existing_map,
    _composite_key,
    _diff_records,
    _fetch_existing_records,
    sync_instructeurs,
)


def create_mock_client():
    """Crée un mock de GristClient avec les attributs utilisés par la tâche"""
    client = MagicMock()
    client.base_url = "https://grist.test/api"
    client.doc_id = "doc123"
    client.headers = {"Authorization": "Bearer test"}
    return client


def create_mock_response(status_code=200, json_data=None, text=""):
    """Crée un mock de réponse HTTP"""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data if json_data is not None else {}
    response.text = text
    return response


def create_mock_client_with_records(response):
    """Crée un mock de GristClient dont get_records renvoie response"""
    client = create_mock_client()
    client.get_records.return_value = response
    return client


def make_instructeur(instructeur_id="i1", groupe_id="g1", email="a@test.fr"):
    """Crée un enregistrement instructeur tel que produit par l'API DN"""
    return {
        "instructeur_id": instructeur_id,
        "instructeur_email": email,
        "groupe_instructeur_id": groupe_id,
        "groupe_instructeur_number": 1,
        "groupe_instructeur_label": "Groupe 1",
    }


class TestCompositeKey:
    """Tests unitaires pour la fonction _composite_key"""

    def test_composite_key_format(self):
        """Test que la clé combine instructeur et groupe"""
        assert _composite_key("i1", "g1") == "i1_g1"

    def test_composite_key_is_unique_per_groupe(self):
        """Test qu'un même instructeur dans deux groupes donne deux clés"""
        assert _composite_key("i1", "g1") != _composite_key("i1", "g2")


class TestBuildExistingMap:
    """Tests unitaires pour la fonction _build_existing_map"""

    def test_build_existing_map_nominal(self):
        """Test d'indexation d'enregistrements complets"""
        records = [
            {
                "id": 10,
                "fields": {"instructeur_id": "i1", "groupe_instructeur_id": "g1"},
            }
        ]

        result = _build_existing_map(records)

        assert "i1_g1" in result
        assert result["i1_g1"]["grist_id"] == 10

    def test_build_existing_map_ignores_incomplete_records(self):
        """Test que les enregistrements sans identifiant sont ignorés"""
        records = [
            {"id": 10, "fields": {"instructeur_id": "i1"}},
            {"id": 11, "fields": {"groupe_instructeur_id": "g1"}},
            {"id": 12, "fields": {}},
        ]

        assert _build_existing_map(records) == {}

    def test_build_existing_map_empty(self):
        """Test avec une liste vide"""
        assert _build_existing_map([]) == {}


class TestDiffRecords:
    """Tests unitaires pour la fonction _diff_records"""

    def test_diff_records_creation(self):
        """Test qu'un instructeur absent de Grist est à créer"""
        new_map = {"i1_g1": make_instructeur()}

        to_delete, to_update, to_create = _diff_records({}, new_map)

        assert to_delete == []
        assert to_update == []
        assert len(to_create) == 1

    def test_diff_records_deletion(self):
        """Test qu'un instructeur absent de DN est à supprimer"""
        existing_map = {
            "i1_g1": {"grist_id": 10, "fields": make_instructeur()},
        }

        to_delete, to_update, to_create = _diff_records(existing_map, {})

        assert to_delete == [10]
        assert to_update == []
        assert to_create == []

    def test_diff_records_update_on_changed_field(self):
        """Test qu'un email modifié déclenche une mise à jour"""
        existing_map = {
            "i1_g1": {
                "grist_id": 10,
                "fields": make_instructeur(email="ancien@test.fr"),
            }
        }
        new_map = {"i1_g1": make_instructeur(email="nouveau@test.fr")}

        to_delete, to_update, to_create = _diff_records(existing_map, new_map)

        assert to_delete == []
        assert to_create == []
        assert len(to_update) == 1
        assert to_update[0]["id"] == 10
        assert to_update[0]["fields"]["instructeur_email"] == "nouveau@test.fr"

    def test_diff_records_no_change(self):
        """Test qu'un enregistrement identique ne génère aucune opération"""
        existing_map = {"i1_g1": {"grist_id": 10, "fields": make_instructeur()}}
        new_map = {"i1_g1": make_instructeur()}

        to_delete, to_update, to_create = _diff_records(existing_map, new_map)

        assert (to_delete, to_update, to_create) == ([], [], [])

    def test_diff_records_ignores_untracked_fields(self):
        """Test qu'un champ hors COMPARED_FIELDS ne déclenche pas de mise à jour"""
        existing = make_instructeur()
        existing["champ_non_suivi"] = "ancien"
        new = make_instructeur()
        new["champ_non_suivi"] = "nouveau"

        _, to_update, _ = _diff_records(
            {"i1_g1": {"grist_id": 10, "fields": existing}}, {"i1_g1": new}
        )

        assert to_update == []


class TestFetchExistingRecords:
    """Tests unitaires pour la fonction _fetch_existing_records"""

    def test_fetch_existing_records_nominal(self):
        """Test de lecture réussie de la table Grist"""
        client = create_mock_client_with_records(
            create_mock_response(json_data={"records": [{"id": 1, "fields": {}}]})
        )

        records = _fetch_existing_records(client, "Table_1")

        assert len(records) == 1
        client.get_records.assert_called_once_with("Table_1")

    def test_fetch_existing_records_raises_on_error(self):
        """Test qu'un échec de lecture lève une exception.

        Retourner une liste vide ferait passer tous les instructeurs en
        création et créerait des doublons dans la table.
        """
        client = create_mock_client_with_records(
            create_mock_response(status_code=500, text="Internal Server Error")
        )

        with pytest.raises(RuntimeError):
            _fetch_existing_records(client, "Table_1")


class TestApplyRecordsDiff:
    """Tests unitaires pour la fonction _apply_records_diff"""

    def test_apply_records_diff_counts_operations(self):
        """Test que le nombre d'opérations appliquées est correct et vérifie les payloads"""
        client = create_mock_client()
        client.delete_records.return_value = create_mock_response()
        client.patch_records.return_value = create_mock_response()
        client.post_records.return_value = create_mock_response()

        count = _apply_records_diff(
            client,
            "Table_1",
            to_delete=[1, 2],
            to_update=[{"id": 3, "fields": {}}],
            to_create=[make_instructeur()],
            log=MagicMock(),
            log_error=MagicMock(),
        )

        assert count == 4
        client.delete_records.assert_called_once()
        assert client.delete_records.call_args.args[0] == "Table_1"
        assert client.delete_records.call_args.args[1] == [1, 2]
        client.patch_records.assert_called_once()
        assert client.patch_records.call_args.args[0] == "Table_1"
        assert client.patch_records.call_args.args[1] == [{"id": 3, "fields": {}}]
        client.post_records.assert_called_once()
        assert client.post_records.call_args.args[0] == "Table_1"
        assert client.post_records.call_args.args[1] == [
            {"fields": make_instructeur()}
        ]

    def test_apply_records_diff_logs_error_on_failure(self):
        """Test qu'un échec Grist est logué et non compté"""
        client = create_mock_client()
        client.post_records.return_value = create_mock_response(
            status_code=400, text="Bad Request"
        )
        log_error = MagicMock()

        count = _apply_records_diff(
            client,
            "Table_1",
            to_delete=[],
            to_update=[],
            to_create=[make_instructeur()],
            log=MagicMock(),
            log_error=log_error,
        )

        assert count == 0
        log_error.assert_called_once()

    def test_apply_records_diff_no_operation(self):
        """Test qu'aucune requête n'est envoyée sans changement"""
        client = create_mock_client()

        count = _apply_records_diff(
            client,
            "Table_1",
            to_delete=[],
            to_update=[],
            to_create=[],
            log=MagicMock(),
            log_error=MagicMock(),
        )

        assert count == 0
        client.delete_records.assert_not_called()
        client.patch_records.assert_not_called()
        client.post_records.assert_not_called()


class TestSyncInstructeurs:
    """Tests unitaires pour la fonction sync_instructeurs"""

    @patch("sync.tasks.instructeurs.extract_instructeurs_from_demarche")
    def test_sync_instructeurs_no_instructeur(self, mock_extract):
        """Test qu'aucun instructeur côté DN retourne un résultat à zéro"""
        mock_extract.return_value = []

        result = sync_instructeurs(
            create_mock_client(), "Table_1", 12345, MagicMock(), MagicMock()
        )

        assert result == {"total": 0, "created": 0, "updated": 0, "deleted": 0}

    @patch("sync.tasks.instructeurs.extract_instructeurs_from_demarche")
    def test_sync_instructeurs_creates_new(self, mock_extract):
        """Test qu'un instructeur absent de Grist est créé"""
        mock_extract.return_value = [make_instructeur()]
        client = create_mock_client_with_records(
            create_mock_response(json_data={"records": []})
        )
        client.post_records.return_value = create_mock_response()

        result = sync_instructeurs(
            client, "Table_1", 12345, MagicMock(), MagicMock()
        )

        assert result["total"] == 1
        assert result["created"] == 1
        assert result["updated"] == 0
        assert result["deleted"] == 0

    @patch("sync.tasks.instructeurs.extract_instructeurs_from_demarche")
    def test_sync_instructeurs_no_change(self, mock_extract):
        """Test qu'un état identique ne génère aucune opération"""
        mock_extract.return_value = [make_instructeur()]
        client = create_mock_client_with_records(
            create_mock_response(json_data={"records": [{"id": 10, "fields": make_instructeur()}]})
        )

        result = sync_instructeurs(
            client, "Table_1", 12345, MagicMock(), MagicMock()
        )

        assert result["created"] == 0
        assert result["updated"] == 0
        assert result["deleted"] == 0

    @patch("sync.tasks.instructeurs.extract_instructeurs_from_demarche")
    def test_sync_instructeurs_propagates_read_error(self, mock_extract):
        """Test qu'une erreur de lecture Grist remonte à l'appelant"""
        mock_extract.return_value = [make_instructeur()]
        client = create_mock_client_with_records(
            create_mock_response(status_code=500, text="error")
        )

        with pytest.raises(RuntimeError):
            sync_instructeurs(
                client, "Table_1", 12345, MagicMock(), MagicMock()
            )
