from unittest.mock import MagicMock, patch

from grist.schema import update_grist_tables_from_schema


def _make_column_types(*, dossier=None, champs=None, annotations=None,
                       repetable_blocks=None):
    """Helper pour construire un dict column_types minimal."""
    return {
        "dossier": dossier or [{"id": "dossier_number", "type": "Int"}],
        "champs": champs or [{"id": "champ_id", "type": "Text"}],
        "annotations": annotations or [{"id": "dossier_number", "type": "Int"}],
        "has_repetable_blocks": bool(repetable_blocks),
        "repetable_blocks": repetable_blocks or {},
    }


def _make_client(existing_tables=None):
    """Mock GristClient avec les attributs requis."""
    client = MagicMock()
    client.base_url = "https://grist.test.com"
    client.doc_id = "doc123"
    client.headers = {"Authorization": "Bearer test"}
    client.list_tables.return_value = existing_tables or []
    client.create_table.return_value = {
        "tables": [{"id": "created_table"}]
    }
    return client


class TestUpdateGristTablesFromSchema:
    """Tests pour update_grist_tables_from_schema (grist/schema.py)."""

    @patch("sync.demandeurs.create_demandeurs_columns")
    def test_creates_all_tables_when_none_exist(self, mock_demandeurs):
        """Crée toutes les tables quand aucune n'existe."""
        mock_demandeurs.return_value = (
            [{"id": "nom", "type": "Text"}], "PersonnePhysique"
        )

        client = _make_client()
        column_types = _make_column_types()

        result = update_grist_tables_from_schema(client, 42, column_types)

        assert result["dossiers"] is not None
        assert result["champs"] is not None
        assert result["demandeurs"] is not None
        assert result["instructeurs"] is not None
        create_calls_str = str(client.create_table.call_args_list)
        assert "Demarche_42_dossiers" in create_calls_str

    @patch("sync.demandeurs.create_demandeurs_columns")
    def test_adds_missing_columns_to_existing_table(self, mock_demandeurs):
        """Ajoute les colonnes manquantes quand la table existe déjà."""
        mock_demandeurs.return_value = (
            [{"id": "nom", "type": "Text"}], "PersonneMorale"
        )

        existing = [{"id": "Demarche_42_dossiers"}]
        client = _make_client(existing_tables=existing)

        column_types = _make_column_types(
            dossier=[
                {"id": "dossier_number", "type": "Int"},
                {"id": "new_col", "type": "Text"},
            ]
        )

        result = update_grist_tables_from_schema(client, 42, column_types)

        create_calls = [
            c for c in client.create_table.call_args_list
            if "dossiers" in str(c)
        ]
        assert len(create_calls) == 0
        client.add_columns.assert_called()

    @patch("sync.demandeurs.create_demandeurs_columns")
    def test_annotations_not_created_when_empty(self, mock_demandeurs):
        """Ne crée pas la table annotations si elle n'a que dossier_number."""
        mock_demandeurs.return_value = (
            [{"id": "nom", "type": "Text"}], "PersonnePhysique"
        )

        client = _make_client()
        annotations = [{"id": "dossier_number", "type": "Int"}]
        column_types = _make_column_types(annotations=annotations)

        result = update_grist_tables_from_schema(client, 42, column_types)

        assert "annotations" not in result
        for c in client.create_table.call_args_list:
            assert "annotations" not in str(c)

    @patch("sync.demandeurs.create_demandeurs_columns")
    def test_avis_table_not_created_when_missing(self, mock_demandeurs):
        """Ne crée pas la table avis si elle n'existe pas déjà."""
        mock_demandeurs.return_value = (
            [{"id": "nom", "type": "Text"}], "PersonneMorale"
        )

        client = _make_client()
        column_types = _make_column_types()

        result = update_grist_tables_from_schema(client, 42, column_types)

        assert result["avis"] is None
        for c in client.create_table.call_args_list:
            assert "avis" not in str(c)

    @patch("sync.demandeurs.create_demandeurs_columns")
    def test_repetable_blocks_create_tables(self, mock_demandeurs):
        """Crée les tables pour chaque bloc répétable."""
        mock_demandeurs.return_value = (
            [{"id": "nom", "type": "Text"}], "PersonnePhysique"
        )

        client = _make_client()
        block_cols = [{"id": "dossier_number", "type": "Int"}]
        column_types = _make_column_types(
            repetable_blocks={
                "block1": {
                    "original_label": "Documents",
                    "columns": block_cols,
                }
            }
        )

        result = update_grist_tables_from_schema(client, 42, column_types)

        assert "repetable_blocks" in result
        assert "block1" in result["repetable_blocks"]

    @patch("sync.demandeurs.create_demandeurs_columns")
    def test_sync_metadata_created(self, mock_demandeurs):
        """La table Sync_metadata est toujours créée exactement une fois."""
        mock_demandeurs.return_value = (
            [{"id": "nom", "type": "Text"}], "PersonnePhysique"
        )

        client = _make_client()
        column_types = _make_column_types()

        result = update_grist_tables_from_schema(client, 42, column_types)

        assert "sync_metadata" in result
        create_calls = [
            str(c) for c in client.create_table.call_args_list
            if "Sync_metadata" in str(c)
        ]
        assert len(create_calls) == 1

    @patch("sync.demandeurs.create_demandeurs_columns")
    def test_dict_format_list_tables(self, mock_demandeurs):
        """Gère le format {'tables': [...]} retourné par list_tables."""
        mock_demandeurs.return_value = (
            [{"id": "nom", "type": "Text"}], "PersonneMorale"
        )

        client = _make_client()
        client.list_tables.return_value = {
            "tables": [{"id": "Demarche_42_dossiers"}]
        }

        column_types = _make_column_types()

        result = update_grist_tables_from_schema(client, 42, column_types)

        assert result["dossiers"] == "Demarche_42_dossiers"
        create_calls = [
            c for c in client.create_table.call_args_list
            if "dossiers" in str(c)
        ]
        assert len(create_calls) == 0

    @patch("sync.demandeurs.create_demandeurs_columns")
    def test_returns_correct_keys(self, mock_demandeurs):
        """Le résultat contient toutes les clés attendues."""
        mock_demandeurs.return_value = (
            [{"id": "nom", "type": "Text"}], "PersonnePhysique"
        )

        client = _make_client()
        column_types = _make_column_types(
            annotations=[
                {"id": "dossier_number", "type": "Int"},
                {"id": "avis", "type": "Text"},
            ]
        )

        result = update_grist_tables_from_schema(client, 42, column_types)

        expected_keys = {
            "dossiers", "champs", "demandeurs", "demandeur_type",
            "instructeurs", "sync_metadata", "annotations",
        }
        assert expected_keys.issubset(result.keys())
