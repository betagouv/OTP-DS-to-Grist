from unittest.mock import MagicMock, patch

import pytest

from grist.columns import (
    COLUMNS_TABLE,
    ID_SUFFIX,
    VIEW_FIELDS_TABLE,
    hide_columns_ending_with,
    hide_columns_with_id,
    untie_column_ids,
)

CHAMPS = "grist.columns"


def _client(*lines: tuple[str, str, int]) -> MagicMock:
    """Client factice : `run_sql` renvoie les champs de lignes (tableId, colId, fieldId)."""
    client = MagicMock()
    client.run_sql.return_value = [
        {"fieldId": field_id, "tableId": table_id, "colId": col_id}
        for table_id, col_id, field_id in lines
    ]
    response = MagicMock()
    response.status_code = 200
    client.apply_user_actions.return_value = response
    return client


def _removed_field_ids(client: MagicMock) -> list[int]:
    """Ids de lignes de champ renvoyés par la seule action d'écriture envoyée."""
    (actions,) = client.apply_user_actions.call_args.args[0]
    return actions[2]


class TestHideColumnsWithId:
    """Tests unitaires pour grist.columns.hide_columns_with_id"""

    def test_delegates_with_the_standard_suffix(self):
        """le suffixe `_id` est fourni par la fonction, pas par l'appelant"""
        client = MagicMock()
        with patch(f"{CHAMPS}.hide_columns_ending_with", return_value=4) as mock_hide:
            assert hide_columns_with_id(client) == 4
        mock_hide.assert_called_once_with(client, suffix=ID_SUFFIX)


class TestHideColumnsEndingWith:
    """Tests unitaires pour grist.columns.hide_columns_ending_with"""

    def test_one_read_and_one_write_for_several_columns(self):
        """N colonnes masquées -> une seule lecture et une seule écriture"""
        client = _client(
            ("T1", "dossier_id", 65),
            ("T2", "instructeur_id", 66),
            ("T2", "block_row_id", 67),
        )
        with patch(f"{CHAMPS}.log"):
            assert hide_columns_ending_with(client, suffix=ID_SUFFIX) == 3
        assert client.run_sql.call_count == 1
        assert client.apply_user_actions.call_count == 1
        assert _removed_field_ids(client) == [65, 66, 67]

    def test_reads_the_fields_of_the_primary_views(self):
        """la lecture remonte les champs des vues principales, une seule fois"""
        client = _client(("T1", "dossier_id", 65))
        with patch(f"{CHAMPS}.log"):
            hide_columns_ending_with(client, suffix=ID_SUFFIX)
        assert client.run_sql.call_count == 1
        sql = client.run_sql.call_args.args[0]
        for table in (
            "_grist_Tables",
            "_grist_Views_section",
            "_grist_Views_section_field",
            "_grist_Tables_column",
        ):
            assert table in sql
        assert "t.primaryViewId" in sql
        assert "t.primaryViewId <> 0" in sql

    def test_deletes_view_field_rows(self):
        """les lignes supprimées sont celles des champs de vue, pas celles des colonnes"""
        client = _client(("T1", "dossier_id", 65))
        with patch(f"{CHAMPS}.log"):
            hide_columns_ending_with(client, suffix=ID_SUFFIX)
        (actions,) = client.apply_user_actions.call_args.args[0]
        assert actions == ["BulkRemoveRecord", VIEW_FIELDS_TABLE, [65]]

    def test_hides_the_id_columns_of_every_table(self):
        """aucune table n'est écartée : le document est partagé entre démarches"""
        client = _client(
            ("Demarche_1_dossiers", "dossier_id", 65),
            ("Demarche_2_dossiers", "dossier_id", 66),
        )
        with patch(f"{CHAMPS}.log"):
            assert hide_columns_ending_with(client, suffix=ID_SUFFIX) == 2
        assert _removed_field_ids(client) == [65, 66]

    def test_keeps_only_columns_ending_with_the_suffix(self):
        """le filtrage est exact et sensible à la casse, contrairement au LIKE de SQLite"""
        client = _client(
            ("T1", "dossier_id", 65),
            ("T1", "dossier_identifiant", 66),
            ("T1", "identifiant", 67),
            ("T1", "id", 68),
            ("T1", "dossierIdx", 69),
        )
        with patch(f"{CHAMPS}.log"):
            assert hide_columns_ending_with(client, suffix=ID_SUFFIX) == 1
        assert _removed_field_ids(client) == [65]

    def test_accepts_another_suffix(self):
        """le suffixe passé par l'appelant intermédiaire est appliqué"""
        client = _client(("T1", "dossier_id", 65), ("T1", "dossier_ref", 66))
        with patch(f"{CHAMPS}.log"):
            assert hide_columns_ending_with(client, suffix="_ref") == 1
        assert _removed_field_ids(client) == [66]

    def test_nothing_to_hide_makes_no_write(self):
        """tout est déjà masqué -> aucune écriture"""
        client = _client(("T1", "dossier_number", 65))
        with patch(f"{CHAMPS}.log"), patch(f"{CHAMPS}.log_verbose") as mock_verbose:
            assert hide_columns_ending_with(client, suffix=ID_SUFFIX) == 0
        assert client.apply_user_actions.call_count == 0
        assert mock_verbose.call_count == 1

    def test_logs_the_hidden_columns(self):
        """les colonnes masquées sont nommées, pour être vérifiables d'un coup d'œil"""
        client = _client(("T1", "dossier_id", 65))
        with patch(f"{CHAMPS}.log") as mock_log:
            hide_columns_ending_with(client, suffix=ID_SUFFIX)
        assert "T1.dossier_id" in mock_log.call_args.args[0]

    def test_grist_error_is_reported_with_its_cause(self):
        """un refus de Grist remonte la cause, sans être avalé"""
        client = _client(("T1", "dossier_id", 65))
        response = client.apply_user_actions.return_value
        response.status_code = 500
        response.text = "Cannot remove raw view section field"
        response.raise_for_status.side_effect = Exception("HTTP 500")
        with patch(f"{CHAMPS}.log"), patch(f"{CHAMPS}.log_error") as mock_error:
            with pytest.raises(Exception):
                hide_columns_ending_with(client, suffix=ID_SUFFIX)
        assert "Cannot remove raw view section field" in mock_error.call_args.args[0]


def _tied_client(*lines: tuple[str, str, int]) -> MagicMock:
    """Client factice : `run_sql` renvoie des colonnes liées (tableId, colId, colRef)."""
    client = MagicMock()
    client.run_sql.return_value = [
        {"colRef": col_ref, "tableId": table_id, "colId": col_id}
        for table_id, col_id, col_ref in lines
    ]
    response = MagicMock()
    response.status_code = 200
    client.apply_user_actions.return_value = response
    return client


def _untied_col_refs(client: MagicMock) -> list[int]:
    """colRefs déliés par la seule action d'écriture envoyée."""
    (action,) = client.apply_user_actions.call_args.args[0]
    return action[2]


class TestUntieColumnIds:
    """Tests unitaires pour grist.columns.untie_column_ids"""

    def test_one_read_and_one_write_for_the_whole_document(self):
        """N colonnes de plusieurs tables -> une seule lecture et une seule écriture"""
        client = _tied_client(
            ("Demarche_1_dossiers", "dossier_number", 10),
            ("Demarche_1_champs", "nom", 11),
            ("Demarche_2_annotations", "avis", 12),
        )
        with patch(f"{CHAMPS}.log"):
            assert untie_column_ids(client) == 3
        assert client.run_sql.call_count == 1
        assert client.apply_user_actions.call_count == 1
        assert _untied_col_refs(client) == [10, 11, 12]

    def test_writes_untie_on_column_metadata(self):
        """l'écriture met untieColIdFromLabel à vrai sur les colonnes, une valeur par colonne"""
        client = _tied_client(
            ("Demarche_1_dossiers", "dossier_number", 10),
            ("Demarche_1_champs", "nom", 11),
        )
        with patch(f"{CHAMPS}.log"):
            untie_column_ids(client)
        (action,) = client.apply_user_actions.call_args.args[0]
        assert action == [
            "BulkUpdateRecord",
            COLUMNS_TABLE,
            [10, 11],
            {"untieColIdFromLabel": [True, True]},
        ]

    def test_reads_only_tied_data_columns(self):
        """la lecture écarte en SQL les colonnes déjà déliées et les formules"""
        client = _tied_client()
        with patch(f"{CHAMPS}.log_verbose"):
            untie_column_ids(client)
        sql = client.run_sql.call_args.args[0]
        assert "_grist_Tables_column" in sql
        assert "c.untieColIdFromLabel = 0" in sql
        assert "c.isFormula = 0" in sql

    def test_includes_sync_metadata_table(self):
        """la table de métadonnées de synchro est une table OTP"""
        client = _tied_client(("Sync_metadata", "last_sync_duration", 20))
        with patch(f"{CHAMPS}.log"):
            assert untie_column_ids(client) == 1
        assert _untied_col_refs(client) == [20]

    def test_leaves_user_tables_untouched(self):
        """les tables ajoutées par les utilisateurs gardent leur réglage"""
        client = _tied_client(
            ("Demarche_1_dossiers", "dossier_number", 10),
            ("Suivi_agents", "commentaire", 30),
            ("Table1", "A", 31),
        )
        with patch(f"{CHAMPS}.log"):
            assert untie_column_ids(client) == 1
        assert _untied_col_refs(client) == [10]

    def test_leaves_grist_internal_columns_untouched(self):
        """manualSort et les colonnes gristHelper_ ne sont pas des colonnes OTP"""
        client = _tied_client(
            ("Demarche_1_dossiers", "manualSort", 40),
            ("Demarche_1_dossiers", "gristHelper_Display", 41),
            ("Demarche_1_dossiers", "dossier_number", 42),
        )
        with patch(f"{CHAMPS}.log"):
            assert untie_column_ids(client) == 1
        assert _untied_col_refs(client) == [42]

    def test_nothing_to_untie_makes_no_write(self):
        """tout est déjà délié -> aucune écriture"""
        client = _tied_client(("Table1", "A", 31))
        with patch(f"{CHAMPS}.log"), patch(f"{CHAMPS}.log_verbose") as mock_verbose:
            assert untie_column_ids(client) == 0
        assert client.apply_user_actions.call_count == 0
        assert mock_verbose.call_count == 1

    def test_logs_the_untied_columns(self):
        """les colonnes déliées sont nommées, pour être vérifiables d'un coup d'œil"""
        client = _tied_client(("Demarche_1_champs", "nom", 11))
        with patch(f"{CHAMPS}.log") as mock_log:
            untie_column_ids(client)
        assert "Demarche_1_champs.nom" in mock_log.call_args.args[0]

    def test_grist_error_is_reported_with_its_cause(self):
        """un refus de Grist remonte la cause, sans être avalé"""
        client = _tied_client(("Demarche_1_champs", "nom", 11))
        response = client.apply_user_actions.return_value
        response.status_code = 403
        response.text = "No write access"
        response.raise_for_status.side_effect = Exception("HTTP 403")
        with patch(f"{CHAMPS}.log"), patch(f"{CHAMPS}.log_error") as mock_error:
            with pytest.raises(Exception):
                untie_column_ids(client)
        assert "No write access" in mock_error.call_args.args[0]
