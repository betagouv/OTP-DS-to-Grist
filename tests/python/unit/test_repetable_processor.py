from unittest.mock import MagicMock, patch

import pytest

from repetable_processor import (
    ensure_repetable_columns_exist,
    auto_fix_missing_columns_optimized,
    process_repetables_for_grist,
    process_repetable_data_batch,
    process_repetables_batch,
    get_existing_repetable_rows_improved_no_filter,
)


class TestEnsureRepetableColumnsExist:
    """Tests unitaires pour ensure_repetable_columns_exist"""

    def setup_method(self):
        self.client = MagicMock()

    def _mock_post(self, status=200):
        response = MagicMock()
        response.status_code = status
        response.text = "err"
        return response

    def test_empty_data_no_http(self):
        """aucune donnée -> True sans appel HTTP"""
        result = ensure_repetable_columns_exist(self.client, "blocs", [])
        assert result is True
        self.client.get_columns.assert_not_called()

    def test_all_columns_present_no_post(self):
        """colonnes nécessaires présentes -> True, pas de POST"""
        self.client.get_columns.return_value = {"age": "Int"}
        result = ensure_repetable_columns_exist(
            self.client, "blocs", [{"age": 5}]
        )
        assert result is True
        self.client.add_columns.assert_not_called()

    def test_missing_columns_created_with_inferred_type(self):
        """colonnes manquantes -> POST avec type inféré"""
        self.client.get_columns.return_value = {"autre_col": "Text"}
        self.client.add_columns.return_value = self._mock_post()
        result = ensure_repetable_columns_exist(
            self.client, "blocs", [{"age": 5}]
        )
        assert result is True
        self.client.add_columns.assert_called_once()
        assert self.client.add_columns.call_args.args[0] == "blocs"
        assert self.client.add_columns.call_args.args[1] == [
            {"id": "age", "type": "Int"}
        ]

    def test_get_error_returns_false(self):
        """GET en échec -> False, pas de POST"""
        self.client.get_columns.return_value = {}
        result = ensure_repetable_columns_exist(
            self.client, "blocs", [{"age": 5}]
        )
        assert result is False
        self.client.add_columns.assert_not_called()

    def test_post_error_returns_false(self):
        """POST en échec -> False"""
        self.client.get_columns.return_value = {"autre_col": "Text"}
        self.client.add_columns.return_value = self._mock_post(status=500)
        result = ensure_repetable_columns_exist(
            self.client, "blocs", [{"age": 5}]
        )
        assert result is False


class TestAutoFixMissingColumnsOptimized:
    """Tests unitaires pour auto_fix_missing_columns_optimized"""

    def setup_method(self):
        self.client = MagicMock()

    def _mock_post(self, status=200):
        response = MagicMock()
        response.status_code = status
        response.text = "err"
        return response

    def test_get_error_returns_false_none(self):
        """GET en échec -> (False, None), pas de POST"""
        self.client.get_columns.return_value = {}
        success, response = auto_fix_missing_columns_optimized(
            self.client, "dossiers", {"records": []}
        )
        assert (success, response) == (False, None)
        self.client.add_columns.assert_not_called()

    def test_adds_missing_columns_then_records(self):
        """colonnes manquantes -> POST colonnes puis POST records"""
        self.client.get_columns.return_value = {"deja_la": "Text"}
        self.client.add_columns.return_value = self._mock_post()
        records_post_response = self._mock_post(status=201)
        self.client.post_records.return_value = records_post_response
        payload = {"records": [{"fields": {"nom": "x", "age": 5}}]}
        success, response = auto_fix_missing_columns_optimized(
            self.client, "dossiers", payload
        )
        assert success is True
        assert response is records_post_response
        self.client.add_columns.assert_called_once()
        assert self.client.add_columns.call_args.args[0] == "dossiers"
        columns = self.client.add_columns.call_args.args[1]
        types_by_id = {c["id"]: c["type"] for c in columns}
        assert types_by_id == {"nom": "Text", "age": "Int"}
        self.client.post_records.assert_called_once_with("dossiers", payload["records"])

    def test_no_missing_columns_only_records(self):
        """aucune colonne manquante -> pas de POST colonnes"""
        self.client.get_columns.return_value = {"nom": "Text", "age": "Int"}
        records_post_response = self._mock_post(status=201)
        self.client.post_records.return_value = records_post_response
        payload = {"records": [{"fields": {"nom": "x", "age": 5}}]}
        success, response = auto_fix_missing_columns_optimized(
            self.client, "dossiers", payload
        )
        assert (success, response) == (True, records_post_response)
        self.client.add_columns.assert_not_called()
        self.client.post_records.assert_called_once_with("dossiers", payload["records"])

    def test_records_post_error_returns_false(self):
        """POST records en échec -> (False, response)"""
        self.client.get_columns.return_value = {"deja_la": "Text"}
        self.client.add_columns.return_value = self._mock_post()
        records_post_response = self._mock_post(status=400)
        self.client.post_records.return_value = records_post_response
        payload = {"records": [{"fields": {"nom": "x"}}]}
        success, response = auto_fix_missing_columns_optimized(
            self.client, "dossiers", payload
        )
        assert (success, response) == (False, records_post_response)
        self.client.add_columns.assert_called_once()

    def test_columns_post_error_no_records(self):
        """POST colonnes en échec -> (False, response), pas de POST records"""
        self.client.get_columns.return_value = {"deja_la": "Text"}
        columns_post_response = self._mock_post(status=400)
        self.client.add_columns.return_value = columns_post_response
        success, response = auto_fix_missing_columns_optimized(
            self.client, "dossiers", {"records": [{"fields": {"nom": "x"}}]}
        )
        assert (success, response) == (False, columns_post_response)
        self.client.add_columns.assert_called_once()
        self.client.post_records.assert_not_called()


class TestProcessRepetablesForGrist:
    """Tests unitaires pour la partie récupération/ajout de colonnes de process_repetables_for_grist"""

    def setup_method(self):
        self.client = MagicMock()
        self.client.base_url = "https://grist.example.com"
        self.client.doc_id = "doc1"

    def _mock_post(self, status=200):
        response = MagicMock()
        response.status_code = status
        response.text = "err"
        return response

    def _call(self):
        dossier_data = {"number": 123, "champs": []}
        column_types = [{"id": "champ_1", "type": "Text"}, {"id": "champ_2", "type": "Text"}]
        with (
            patch(
                "repetable_processor.get_existing_repetable_rows_improved_no_filter",
                return_value={},
            ),
        ):
            result = process_repetables_for_grist(
                self.client, dossier_data, "blocs", column_types
            )
        return result, self.client.post_records

    def test_get_error_no_post_columns(self):
        """GET en échec -> aucune colonne ajoutée, aucun POST, pas de données insérées"""
        self.client.get_columns.return_value = {}
        result, mock_post = self._call()
        assert result == (0, 0)
        self.client.add_columns.assert_not_called()
        mock_post.assert_not_called()

    def test_missing_columns_posted_with_geo(self):
        """colonnes manquantes -> POST avec les colonnes manquantes et les colonnes géo"""
        self.client.get_columns.return_value = {"champ_1": "Text"}
        self.client.add_columns.return_value = self._mock_post()
        result, mock_post = self._call()
        assert result == (0, 0)
        self.client.add_columns.assert_called_once()
        assert self.client.add_columns.call_args.args[0] == "blocs"
        columns = self.client.add_columns.call_args.args[1]
        column_ids = {c["id"] for c in columns}
        assert "champ_2" in column_ids
        assert "geo_id" in column_ids
        assert "geo_surface" in column_ids
        mock_post.assert_not_called()


class TestGetExistingRepetableRowsImprovedNoFilter:
    """Tests unitaires pour get_existing_repetable_rows_improved_no_filter"""

    def setup_method(self):
        self.client = MagicMock()
        self.client.base_url = "https://grist.example.com"
        self.client.doc_id = "doc1"
        self.client.headers = {"Authorization": "Bearer test"}

    def _mock_response(self, status=200, records=None):
        response = MagicMock()
        response.status_code = status
        response.text = "err"
        response.json.return_value = {"records": records or []}
        return response

    def test_raises_without_doc_id(self):
        """sans doc_id -> ValueError, pas d'appel HTTP"""
        self.client.doc_id = None
        self.client.get_records.return_value = self._mock_response(200)
        with pytest.raises(ValueError):
            get_existing_repetable_rows_improved_no_filter(self.client, "blocs")
        self.client.get_records.assert_not_called()

    def test_http_error_returns_empty_dict(self):
        """réponse non-200 -> {}"""
        self.client.get_records.return_value = self._mock_response(500)
        result = get_existing_repetable_rows_improved_no_filter(self.client, "blocs")
        assert result == {}
        self.client.get_records.assert_called_once_with("blocs")

    def test_success_builds_composite_keys(self):
        """200 -> dict des clés composites vers l'id de l'enregistrement"""
        records = [
            {
                "id": 42,
                "fields": {
                    "dossier_number": "123",
                    "block_label": "Maquettes",
                    "block_row_id": "row_1",
                    "block_row_index": 1,
                },
            }
        ]
        self.client.get_records.return_value = self._mock_response(200, records)
        result = get_existing_repetable_rows_improved_no_filter(self.client, "blocs")
        assert result["123_Maquettes_row_1"] == 42
        assert result["123_maquettes_row_1"] == 42
        assert result["123_Maquettes_index_1"] == 42
        assert result["row_1"] == 42

    def test_success_builds_geo_keys(self):
        """200 avec géométrie -> clés géo"""
        records = [
            {
                "id": 7,
                "fields": {
                    "dossier_number": "123",
                    "block_label": "Maquettes",
                    "block_row_id": "row_1_geo1",
                    "field_name": "carte",
                    "geo_id": "g1",
                },
            }
        ]
        self.client.get_records.return_value = self._mock_response(200, records)
        result = get_existing_repetable_rows_improved_no_filter(self.client, "blocs")
        assert result["123_Maquettes_row_1_geo1"] == 7
        assert result["123_maquettes_carte_g1"] == 7


class TestProcessRepetableDataBatchRecords:
    """Tests unitaires des opérations records (upsert) de process_repetable_data_batch"""

    def setup_method(self):
        self.client = MagicMock()
        self.client.base_url = "https://grist.example.com"
        self.client.doc_id = "doc1"
        self.client.headers = {"Authorization": "Bearer test"}

    def _mock_response(self, status=200):
        response = MagicMock()
        response.status_code = status
        response.text = "err"
        return response

    @staticmethod
    def _dossier(rows):
        return {
            "number": 123,
            "champs": [
                {
                    "__typename": "RepetitionChamp",
                    "id": "bloc_1",
                    "label": "Maquettes",
                    "rows": rows,
                }
            ],
        }

    @staticmethod
    def _simple_row():
        return {
            "id": "row_1",
            "champs": [
                {"__typename": "TextChamp", "label": "Nom", "stringValue": "Toto"},
            ],
        }

    def _expected_record(self):
        return {
            "dossier_number": 123,
            "block_id": "bloc_1",
            "block_row_index": 1,
            "block_row_id": "row_1",
            "nom": "Toto",
        }

    def test_create_new_record_when_no_existing_row(self):
        """aucune ligne existante -> POST records avec les champs de la ligne"""
        column_types = [{"id": "nom", "type": "Text"}]
        self.client.post_records.return_value = self._mock_response(201)
        with (
            patch(
                "repetable_processor.get_existing_repetable_rows_improved_no_filter",
                return_value={},
            ),
        ):
            success, errors = process_repetable_data_batch(
                self.client, self._dossier([self._simple_row()]), "blocs", column_types
            )
        assert (success, errors) == (1, 0)
        self.client.post_records.assert_called_once()
        assert self.client.post_records.call_args.args[0] == "blocs"
        assert self.client.post_records.call_args.args[1] == [
            {"fields": self._expected_record()}
        ]
        self.client.patch_records.assert_not_called()

    def test_update_existing_record_when_found(self):
        """ligne existante -> PATCH records avec l'id trouvé"""
        column_types = [{"id": "nom", "type": "Text"}]
        existing_rows = {"123_maquettes_row_1": 42}
        self.client.patch_records.return_value = self._mock_response(200)
        with (
            patch(
                "repetable_processor.get_existing_repetable_rows_improved_no_filter",
                return_value=existing_rows,
            ),
        ):
            success, errors = process_repetable_data_batch(
                self.client, self._dossier([self._simple_row()]), "blocs", column_types
            )
        assert (success, errors) == (1, 0)
        self.client.patch_records.assert_called_once()
        assert self.client.patch_records.call_args.args[0] == "blocs"
        assert self.client.patch_records.call_args.args[1] == [
            {"id": 42, "fields": self._expected_record()}
        ]
        self.client.post_records.assert_not_called()

    def test_create_error_increments_error_count(self):
        """POST en échec -> compteur d'erreurs incrémenté"""
        column_types = [{"id": "nom", "type": "Text"}]
        self.client.post_records.return_value = self._mock_response(500)
        with (
            patch(
                "repetable_processor.get_existing_repetable_rows_improved_no_filter",
                return_value={},
            ),
        ):
            success, errors = process_repetable_data_batch(
                self.client, self._dossier([self._simple_row()]), "blocs", column_types
            )
        assert (success, errors) == (0, 1)

    def test_geo_creates_one_record_per_geometry(self):
        """champ carte -> POST records avec les données géo"""
        geo_row = {
            "id": "row_1",
            "champs": [
                {
                    "__typename": "CarteChamp",
                    "label": "Carte",
                    "geoAreas": [
                        {
                            "id": "g1",
                            "description": "zone A",
                            "geometry": {"type": "Point", "coordinates": [1.0, 2.0]},
                            "surface": 150,
                        }
                    ],
                }
            ],
        }
        column_types = [
            {"id": "carte", "type": "Text"},
            {"id": "geo_id", "type": "Text"},
            {"id": "geo_surface", "type": "Text"},
        ]
        self.client.post_records.return_value = self._mock_response(201)
        with (
            patch(
                "repetable_processor.get_existing_repetable_rows_improved_no_filter",
                return_value={},
            ),
        ):
            success, errors = process_repetable_data_batch(
                self.client, self._dossier([geo_row]), "blocs", column_types
            )
        assert (success, errors) == (1, 0)
        self.client.post_records.assert_called_once()
        records = self.client.post_records.call_args.args[1]
        fields = records[0]["fields"]
        assert fields["block_row_id"] == "row_1_geo1"
        assert fields["carte"] == "zone A"
        assert fields["geo_id"] == "g1"
        assert fields["geo_surface"] == "150"


class TestProcessRepetablesBatchRecords:
    """Tests unitaires des opérations records (lot) de process_repetables_batch"""

    def setup_method(self):
        self.client = MagicMock()
        self.client.base_url = "https://grist.example.com"
        self.client.doc_id = "doc1"
        self.client.headers = {"Authorization": "Bearer test"}

    def _mock_response(self, status=200, text="err"):
        response = MagicMock()
        response.status_code = status
        response.text = text
        return response

    @staticmethod
    def _dossier():
        return {
            "number": 123,
            "champs": [
                {
                    "__typename": "RepetitionChamp",
                    "id": "bloc_1",
                    "label": "Maquettes",
                    "rows": [
                        {
                            "id": "row_1",
                            "champs": [
                                {"__typename": "TextChamp", "label": "Nom", "stringValue": "Toto"},
                            ],
                        }
                    ],
                }
            ],
        }

    @staticmethod
    def _table_ids():
        return {"maquettes": "Demarche_123_maquettes"}

    @staticmethod
    def _column_types():
        return {"maquettes": {"columns": [{"id": "nom", "type": "Text"}]}}

    def _expected_record(self):
        return {
            "dossier_number": 123,
            "block_id": "bloc_1",
            "block_row_index": 1,
            "block_row_id": "row_1",
            "nom": "Toto",
        }

    def test_create_batch_records(self):
        """aucune ligne existante -> POST lot avec les enregistrements à créer"""
        self.client.post_records.return_value = self._mock_response(201)
        with (
            patch(
                "repetable_processor.get_existing_repetable_rows_improved_no_filter",
                return_value={},
            ),
        ):
            success, errors = process_repetables_batch(
                self.client, [self._dossier()], self._table_ids(), self._column_types()
            )
        assert (success, errors) == (1, 0)
        self.client.post_records.assert_called_once()
        assert self.client.post_records.call_args.args[0] == "Demarche_123_maquettes"
        assert self.client.post_records.call_args.args[1] == [
            {"fields": self._expected_record()}
        ]
        self.client.patch_records.assert_not_called()

    def test_update_batch_records(self):
        """ligne existante -> PATCH lot avec les ids trouvés"""
        existing_rows = {"123_maquettes_row_1": 42}
        self.client.patch_records.return_value = self._mock_response(200)
        with (
            patch(
                "repetable_processor.get_existing_repetable_rows_improved_no_filter",
                return_value=existing_rows,
            ),
        ):
            success, errors = process_repetables_batch(
                self.client, [self._dossier()], self._table_ids(), self._column_types()
            )
        assert (success, errors) == (1, 0)
        self.client.patch_records.assert_called_once()
        assert self.client.patch_records.call_args.args[0] == "Demarche_123_maquettes"
        assert self.client.patch_records.call_args.args[1] == [
            {"id": 42, "fields": self._expected_record()}
        ]
        self.client.post_records.assert_not_called()

    def test_update_batch_error_falls_back_to_individual(self):
        """PATCH lot en échec -> repli sur des PATCH individuels"""
        existing_rows = {"123_maquettes_row_1": 42}
        self.client.patch_records.side_effect = [
            self._mock_response(400),
            self._mock_response(200),
        ]
        with (
            patch(
                "repetable_processor.get_existing_repetable_rows_improved_no_filter",
                return_value=existing_rows,
            ),
        ):
            success, errors = process_repetables_batch(
                self.client, [self._dossier()], self._table_ids(), self._column_types()
            )
        assert (success, errors) == (1, 0)
        assert self.client.patch_records.call_count == 2
        assert self.client.patch_records.call_args_list[1].args[0] == (
            "Demarche_123_maquettes"
        )
        assert self.client.patch_records.call_args_list[1].args[1] == [
            {"id": 42, "fields": self._expected_record()}
        ]

    def test_create_error_increments_error_count(self):
        """POST lot en échec -> compteur d'erreurs incrémenté"""
        self.client.post_records.return_value = self._mock_response(500)
        with (
            patch(
                "repetable_processor.get_existing_repetable_rows_improved_no_filter",
                return_value={},
            ),
        ):
            success, errors = process_repetables_batch(
                self.client, [self._dossier()], self._table_ids(), self._column_types()
            )
        assert (success, errors) == (0, 1)

    def test_create_auto_fix_on_invalid_column(self):
        """erreur 'Invalid column' -> auto-fix des colonnes manquantes"""
        self.client.post_records.return_value = self._mock_response(
            400, text="Invalid column"
        )
        with (
            patch(
                "repetable_processor.get_existing_repetable_rows_improved_no_filter",
                return_value={},
            ),
            patch(
                "repetable_processor.auto_fix_missing_columns_optimized",
                return_value=(True, None),
            ) as mock_auto_fix,
        ):
            success, errors = process_repetables_batch(
                self.client, [self._dossier()], self._table_ids(), self._column_types()
            )
        assert (success, errors) == (1, 0)
        mock_auto_fix.assert_called_once()
        assert mock_auto_fix.call_args.args[1] == "Demarche_123_maquettes"
        assert self.client.post_records.call_args.args[1] == [
            {"fields": self._expected_record()}
        ]


class TestProcessRepetablesForGristRecords:
    """Tests unitaires des opérations records (upsert) de process_repetables_for_grist"""

    def setup_method(self):
        self.client = MagicMock()
        self.client.base_url = "https://grist.example.com"
        self.client.doc_id = "doc1"
        self.client.headers = {"Authorization": "Bearer test"}
        self.client.get_columns.return_value = {}

    def _mock_response(self, status=200, json_data=None):
        response = MagicMock()
        response.status_code = status
        response.text = "err"
        response.json.return_value = json_data
        return response

    @staticmethod
    def _dossier(rows):
        return {
            "number": 123,
            "champs": [
                {
                    "__typename": "RepetitionChamp",
                    "id": "bloc_1",
                    "label": "Maquettes",
                    "rows": rows,
                }
            ],
        }

    @staticmethod
    def _simple_row():
        return {
            "id": "row_1",
            "champs": [
                {"__typename": "TextChamp", "label": "Nom", "stringValue": "Toto"},
            ],
        }

    def _expected_record(self):
        return {
            "dossier_number": 123,
            "block_id": "bloc_1",
            "block_label": "Maquettes",
            "block_row_index": 1,
            "block_row_id": "row_1",
            "nom": "Toto",
        }

    def test_create_new_record_when_no_existing_row(self):
        """aucune ligne existante -> POST records et mémorisation de l'id créé"""
        column_types = [{"id": "nom", "type": "Text"}]
        existing_rows = {}
        self.client.post_records.return_value = self._mock_response(
            201, {"records": [{"id": 99}]}
        )
        with (
            patch(
                "repetable_processor.get_existing_repetable_rows_improved_no_filter",
                return_value=existing_rows,
            ),
        ):
            success, errors = process_repetables_for_grist(
                self.client, self._dossier([self._simple_row()]), "blocs", column_types
            )
        assert (success, errors) == (1, 0)
        self.client.post_records.assert_called_once()
        assert self.client.post_records.call_args.args[0] == "blocs"
        assert self.client.post_records.call_args.args[1] == [
            {"fields": self._expected_record()}
        ]
        assert existing_rows["123_maquettes_row_1"] == 99
        assert existing_rows["row_1"] == 99
        self.client.patch_records.assert_not_called()

    def test_update_existing_record_when_found(self):
        """ligne existante -> PATCH records avec l'id trouvé"""
        column_types = [{"id": "nom", "type": "Text"}]
        existing_rows = {"123_maquettes_row_1": 42}
        self.client.patch_records.return_value = self._mock_response(200)
        with (
            patch(
                "repetable_processor.get_existing_repetable_rows_improved_no_filter",
                return_value=existing_rows,
            ),
        ):
            success, errors = process_repetables_for_grist(
                self.client, self._dossier([self._simple_row()]), "blocs", column_types
            )
        assert (success, errors) == (1, 0)
        self.client.patch_records.assert_called_once()
        assert self.client.patch_records.call_args.args[0] == "blocs"
        assert self.client.patch_records.call_args.args[1] == [
            {"id": 42, "fields": self._expected_record()}
        ]
        self.client.post_records.assert_not_called()

    def test_create_error_increments_error_count(self):
        """POST en échec -> compteur d'erreurs incrémenté"""
        column_types = [{"id": "nom", "type": "Text"}]
        self.client.post_records.return_value = self._mock_response(500)
        with (
            patch(
                "repetable_processor.get_existing_repetable_rows_improved_no_filter",
                return_value={},
            ),
        ):
            success, errors = process_repetables_for_grist(
                self.client, self._dossier([self._simple_row()]), "blocs", column_types
            )
        assert (success, errors) == (0, 1)

    def test_geo_creates_record_per_geometry(self):
        """champ carte -> POST records avec les données géo"""
        geo_row = {
            "id": "row_1",
            "champs": [
                {
                    "__typename": "CarteChamp",
                    "label": "Carte",
                    "geoAreas": [
                        {
                            "id": "g1",
                            "description": "zone A",
                            "geometry": {"type": "Point", "coordinates": [1.0, 2.0]},
                            "surface": 150,
                        }
                    ],
                }
            ],
        }
        column_types = [
            {"id": "carte", "type": "Text"},
            {"id": "geo_id", "type": "Text"},
            {"id": "geo_surface", "type": "Text"},
        ]
        self.client.post_records.return_value = self._mock_response(
            201, {"records": [{"id": 7}]}
        )
        with (
            patch(
                "repetable_processor.get_existing_repetable_rows_improved_no_filter",
                return_value={},
            ),
        ):
            success, errors = process_repetables_for_grist(
                self.client, self._dossier([geo_row]), "blocs", column_types
            )
        assert (success, errors) == (1, 0)
        self.client.post_records.assert_called_once()
        records = self.client.post_records.call_args.args[1]
        fields = records[0]["fields"]
        assert fields["block_row_id"] == "row_1_geo1"
        assert fields["carte"] == "zone A"
        assert fields["geo_id"] == "g1"
        assert fields["geo_surface"] == "150"
