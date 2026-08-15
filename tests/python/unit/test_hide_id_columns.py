from unittest.mock import MagicMock, call

from hide_id_columns import IdColumnHider


def _resp(records, status=200):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = {"records": records}
    return response


class TestIdColumnHider:
    """Tests unitaires pour IdColumnHider.hide_id_columns"""

    def setup_method(self):
        self.client = MagicMock()
        self.client.delete_records.return_value.status_code = 200
        self.hider = IdColumnHider(self.client)

    def _mock_fetches(self, tables, columns, sections, fields):
        self.client.get_records.side_effect = [
            _resp(tables),
            _resp(columns),
            _resp(sections),
            _resp(fields),
        ]

    @staticmethod
    def _sample_data():
        tables = [
            {"id": 1, "fields": {"tableId": "Demarche_1_dossiers"}},
            {"id": 2, "fields": {"tableId": "Demarche_1_commentaires"}},
        ]
        columns = [
            {"id": 10, "fields": {"parentId": 1, "colId": "dossier_number"}},
            {"id": 11, "fields": {"parentId": 1, "colId": "annotation_id"}},
            {"id": 12, "fields": {"parentId": 2, "colId": "commentaire_id"}},
            {"id": 13, "fields": {"parentId": 2, "colId": "commentaire"}},
        ]
        sections = [
            {"id": 20, "fields": {"tableRef": 1}},
            {"id": 21, "fields": {"tableRef": 2}},
        ]
        fields = [
            {"id": 30, "fields": {"parentId": 20, "colRef": 10}},
            {"id": 31, "fields": {"parentId": 20, "colRef": 11}},
            {"id": 32, "fields": {"parentId": 21, "colRef": 12}},
        ]
        return tables, columns, sections, fields

    def test_hides_matching_id_columns(self):
        """colonnes *_id cachées via delete_records, les autres ignorées"""
        tables, columns, sections, fields = self._sample_data()
        self._mock_fetches(tables, columns, sections, fields)

        nb_ok, nb_skip = self.hider.hide_id_columns()

        assert (nb_ok, nb_skip) == (2, 0)
        assert self.client.delete_records.call_args_list == [
            call("_grist_Views_section_field", [31]),
            call("_grist_Views_section_field", [32]),
        ]
        assert [c.args[0] for c in self.client.get_records.call_args_list] == [
            "_grist_Tables",
            "_grist_Tables_column",
            "_grist_Views_section",
            "_grist_Views_section_field",
        ]

    def test_skips_when_no_first_section(self):
        """colonne *_id d'une table sans section -> skip"""
        tables = [
            {"id": 1, "fields": {"tableId": "Demarche_1_avis"}},
        ]
        columns = [{"id": 11, "fields": {"parentId": 1, "colId": "avis_id"}}]
        self._mock_fetches(tables, columns, [], [])

        nb_ok, nb_skip = self.hider.hide_id_columns()

        assert (nb_ok, nb_skip) == (0, 1)
        self.client.delete_records.assert_not_called()

    def test_skips_when_no_field_mapping(self):
        """colonne *_id sans champ de section correspondant -> skip"""
        tables = [{"id": 1, "fields": {"tableId": "Demarche_1_dossiers"}}]
        columns = [{"id": 11, "fields": {"parentId": 1, "colId": "annotation_id"}}]
        sections = [{"id": 20, "fields": {"tableRef": 1}}]
        fields = [{"id": 30, "fields": {"parentId": 20, "colRef": 10}}]
        self._mock_fetches(tables, columns, sections, fields)

        nb_ok, nb_skip = self.hider.hide_id_columns()

        assert (nb_ok, nb_skip) == (0, 1)
        self.client.delete_records.assert_not_called()

    def test_filters_by_table_ids(self):
        """table_ids restreint les tables traitées"""
        tables, columns, sections, fields = self._sample_data()
        self._mock_fetches(tables, columns, sections, fields)

        nb_ok, nb_skip = self.hider.hide_id_columns(
            table_ids={"Demarche_1_dossiers"}
        )

        assert (nb_ok, nb_skip) == (1, 0)
        self.client.delete_records.assert_called_once_with(
            "_grist_Views_section_field", [31]
        )

    def test_no_columns_no_delete(self):
        """aucune colonne -> rien à cacher, fetch quand même"""
        self._mock_fetches([], [], [], [])

        nb_ok, nb_skip = self.hider.hide_id_columns()

        assert (nb_ok, nb_skip) == (0, 0)
        assert self.client.get_records.call_count == 4
        self.client.delete_records.assert_not_called()
