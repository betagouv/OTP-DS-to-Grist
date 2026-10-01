from unittest.mock import MagicMock, patch

import pytest

from grist.columns import (
    ID_SUFFIX,
    VIEW_FIELDS_TABLE,
    hide_columns_ending_with,
    hide_columns_with_id,
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
