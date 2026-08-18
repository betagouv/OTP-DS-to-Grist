import pytest
from unittest.mock import MagicMock, patch

from hide_id_columns import IdColumnHider, main


def _make_hider(base_url="https://grist.example.com", api_key="key", doc_id="doc1"):
    return IdColumnHider(base_url, api_key, doc_id)


def _mock_records(records):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"records": records}
    resp.raise_for_status = MagicMock()
    return resp


class TestApiUrl:
    """Tests pour IdColumnHider._api_url"""

    def test_basic_construction(self):
        hider = _make_hider(base_url="https://grist.example.com")
        assert (
            hider._api_url("tables/_grist_Tables/records")
            == "https://grist.example.com/api/docs/doc1/tables/_grist_Tables/records"
        )

    def test_strips_trailing_slash(self):
        hider = _make_hider(base_url="https://grist.example.com/")
        assert (
            hider._api_url("tables/_grist_Tables/records")
            == "https://grist.example.com/api/docs/doc1/tables/_grist_Tables/records"
        )


class TestHideField:
    """Tests pour IdColumnHider._hide_field"""

    def test_successful_delete(self):
        hider = _make_hider()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("hide_id_columns.requests.delete", return_value=mock_resp):
            hider._hide_field(42)

    def test_fallback_to_apply_on_404(self):
        hider = _make_hider()
        del_resp = MagicMock()
        del_resp.status_code = 404
        apply_resp = MagicMock()
        apply_resp.status_code = 200
        with (
            patch("hide_id_columns.requests.delete", return_value=del_resp),
            patch(
                "hide_id_columns.requests.post", return_value=apply_resp
            ) as mock_post,
        ):
            hider._hide_field(42)
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        assert payload[0] == ["RemoveRecord", "_grist_Views_section_field", 42]

    def test_fallback_to_apply_on_405(self):
        hider = _make_hider()
        del_resp = MagicMock()
        del_resp.status_code = 405
        apply_resp = MagicMock()
        apply_resp.status_code = 200
        with (
            patch("hide_id_columns.requests.delete", return_value=del_resp),
            patch(
                "hide_id_columns.requests.post", return_value=apply_resp
            ) as mock_post,
        ):
            hider._hide_field(42)
        mock_post.assert_called_once()


class TestHideIdColumns:
    """Tests pour IdColumnHider.hide_id_columns"""

    def _setup_mocks(self):
        tables_resp = _mock_records(
            [
                {"id": 1, "fields": {"tableId": "Demarche_123_dossiers"}},
                {"id": 2, "fields": {"tableId": "Demarche_123_champs"}},
            ]
        )
        columns_resp = _mock_records(
            [
                {"id": 10, "fields": {"colId": "dossier_number", "parentId": 1}},
                {"id": 11, "fields": {"colId": "some_id", "parentId": 1}},
                {"id": 12, "fields": {"colId": "name", "parentId": 1}},
                {"id": 13, "fields": {"colId": "other_id", "parentId": 2}},
            ]
        )
        sections_resp = _mock_records(
            [
                {"id": 100, "fields": {"tableRef": 1}},
                {"id": 200, "fields": {"tableRef": 2}},
            ]
        )
        fields_resp = _mock_records(
            [
                {"id": 1000, "fields": {"parentId": 100, "colRef": 11}},
                {"id": 1001, "fields": {"parentId": 100, "colRef": 12}},
                {"id": 2000, "fields": {"parentId": 200, "colRef": 13}},
            ]
        )
        return tables_resp, columns_resp, sections_resp, fields_resp

    def test_hides_columns_with_suffix(self):
        hider = _make_hider()
        tables, columns, sections, fields = self._setup_mocks()
        hide_resp = MagicMock()
        hide_resp.status_code = 200

        with (
            patch(
                "hide_id_columns.requests.get",
                side_effect=[tables, columns, sections, fields],
            ),
            patch(
                "hide_id_columns.requests.delete", return_value=hide_resp
            ) as mock_del,
        ):
            ok, skip = hider.hide_id_columns()

        assert ok == 2
        assert skip == 0
        assert mock_del.call_count == 2

    def test_skips_columns_without_suffix(self):
        hider = _make_hider()
        tables, columns, sections, fields = self._setup_mocks()

        with (
            patch(
                "hide_id_columns.requests.get",
                side_effect=[tables, columns, sections, fields],
            ),
            patch("hide_id_columns.requests.delete") as mock_del,
        ):
            ok, skip = hider.hide_id_columns(suffix="_xyz")

        assert ok == 0
        mock_del.assert_not_called()

    def test_respects_table_ids_filter(self):
        hider = _make_hider()
        tables, columns, sections, fields = self._setup_mocks()
        hide_resp = MagicMock()
        hide_resp.status_code = 200

        with (
            patch(
                "hide_id_columns.requests.get",
                side_effect=[tables, columns, sections, fields],
            ),
            patch(
                "hide_id_columns.requests.delete", return_value=hide_resp
            ) as mock_del,
        ):
            ok, skip = hider.hide_id_columns(table_ids={"Demarche_123_champs"})

        assert ok == 1
        assert mock_del.call_count == 1

    def test_skips_when_no_section(self):
        hider = _make_hider()
        tables_resp = _mock_records([{"id": 1, "fields": {"tableId": "t1"}}])
        columns_resp = _mock_records(
            [{"id": 10, "fields": {"colId": "x_id", "parentId": 1}}]
        )
        sections_resp = _mock_records([])
        fields_resp = _mock_records([])

        with (
            patch(
                "hide_id_columns.requests.get",
                side_effect=[tables_resp, columns_resp, sections_resp, fields_resp],
            ),
            patch("hide_id_columns.requests.delete") as mock_del,
        ):
            ok, skip = hider.hide_id_columns()

        assert ok == 0
        assert skip == 1
        mock_del.assert_not_called()

    def test_skips_when_no_field(self):
        hider = _make_hider()
        tables_resp = _mock_records([{"id": 1, "fields": {"tableId": "t1"}}])
        columns_resp = _mock_records(
            [{"id": 10, "fields": {"colId": "x_id", "parentId": 1}}]
        )
        sections_resp = _mock_records(
            [{"id": 100, "fields": {"tableRef": 1}}]
        )
        fields_resp = _mock_records(
            [{"id": 1000, "fields": {"parentId": 100, "colRef": 999}}]
        )

        with (
            patch(
                "hide_id_columns.requests.get",
                side_effect=[tables_resp, columns_resp, sections_resp, fields_resp],
            ),
            patch("hide_id_columns.requests.delete") as mock_del,
        ):
            ok, skip = hider.hide_id_columns()

        assert ok == 0
        assert skip == 1
        mock_del.assert_not_called()

    def test_returns_counts(self):
        hider = _make_hider()
        tables, columns, sections, fields = self._setup_mocks()
        hide_resp = MagicMock()
        hide_resp.status_code = 200

        with (
            patch(
                "hide_id_columns.requests.get",
                side_effect=[tables, columns, sections, fields],
            ),
            patch(
                "hide_id_columns.requests.delete", return_value=hide_resp
            ),
        ):
            result = hider.hide_id_columns()

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result == (2, 0)

    def test_with_empty_document(self):
        hider = _make_hider()
        empty = _mock_records([])

        with (
            patch(
                "hide_id_columns.requests.get",
                side_effect=[empty, empty, empty, empty],
            ),
            patch("hide_id_columns.requests.delete") as mock_del,
        ):
            ok, skip = hider.hide_id_columns()

        assert ok == 0
        assert skip == 0
        mock_del.assert_not_called()


class TestMain:
    """Tests pour la fonction main()"""

    def test_incomplete_config_returns_1(self):
        with patch("hide_id_columns.os.getenv", return_value=None):
            assert main() == 1

    def test_complete_config_returns_0(self):
        env = {
            "GRIST_BASE_URL": "https://grist.example.com",
            "GRIST_API_KEY": "key",
            "GRIST_DOC_ID": "doc1",
        }
        empty = _mock_records([])

        with (
            patch(
                "hide_id_columns.os.getenv",
                side_effect=lambda k: env.get(k),
            ),
            patch("hide_id_columns.load_dotenv"),
            patch(
                "hide_id_columns.requests.get",
                side_effect=[empty, empty, empty, empty],
            ),
        ):
            assert main() == 0
