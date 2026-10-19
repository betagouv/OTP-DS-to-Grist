from unittest.mock import MagicMock, patch

import pytest

from grist.client import GristReadError

from repetable_processor import (
    auto_fix_missing_columns_optimized,
    process_repetables_batch,
    get_existing_repetable_rows,
)


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


class TestGetExistingRepetableRows:
    """Tests unitaires pour get_existing_repetable_rows"""

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
            get_existing_repetable_rows(self.client, "blocs")
        self.client.get_records.assert_not_called()

    def test_http_error_raises_read_error(self):
        """réponse non-200 -> GristReadError (un dict vide ferait recréer
        toutes les lignes répétables du run)"""
        self.client.get_records.return_value = self._mock_response(500)
        with pytest.raises(GristReadError) as error:
            get_existing_repetable_rows(self.client, "blocs")
        assert error.value.table_id == "blocs"
        self.client.get_records.assert_called_once_with("blocs")

    def test_success_builds_only_dossier_row_keys(self):
        """200 -> une seule clé (dossier, block_row_id) par ligne, plus de clés
        à base de block_label (colonne jamais écrite dans les tables de blocs)"""
        records = [
            {
                "id": 42,
                "fields": {
                    "dossier_number": "123",
                    "block_label": "Maquettes",
                    "block_row_id": "row_1",
                    "block_row_index": 1,
                },
            },
            {
                "id": 7,
                "fields": {
                    "dossier_number": "123",
                    "block_row_id": "row_1_geo1",
                    "field_name": "carte",
                    "geo_id": "g1",
                },
            },
        ]
        self.client.get_records.return_value = self._mock_response(200, records)
        result = get_existing_repetable_rows(self.client, "blocs")
        assert result == {"123:row_1": 42, "123:row_1_geo1": 7}

    def test_rows_without_identifiers_are_ignored(self):
        """ligne sans dossier_number ou sans block_row_id -> ignorée"""
        records = [
            {"id": 1, "fields": {"block_row_id": "row_1"}},
            {"id": 2, "fields": {"dossier_number": 123, "block_row_index": 1}},
            {"id": 3, "fields": {"dossier_number": 123, "block_row_id": ""}},
        ]
        self.client.get_records.return_value = self._mock_response(200, records)
        assert get_existing_repetable_rows(self.client, "blocs") == {}

    def test_same_block_row_id_in_two_dossiers_gives_distinct_keys(self):
        """même block_row_id dans deux dossiers -> deux clés distinctes"""
        records = [
            {"id": 1, "fields": {"dossier_number": 123, "block_row_id": "row_1"}},
            {"id": 2, "fields": {"dossier_number": 456, "block_row_id": "row_1"}},
        ]
        self.client.get_records.return_value = self._mock_response(200, records)
        result = get_existing_repetable_rows(self.client, "blocs")
        assert result["123:row_1"] == 1
        assert result["456:row_1"] == 2
        assert "row_1" not in result

    def test_float_dossier_number_is_normalized(self):
        """dossier_number relu en 123.0 -> même clé que 123"""
        records = [
            {"id": 1, "fields": {"dossier_number": 123.0, "block_row_id": "row_1"}},
        ]
        self.client.get_records.return_value = self._mock_response(200, records)
        result = get_existing_repetable_rows(self.client, "blocs")
        assert result["123:row_1"] == 1


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
                "repetable_processor.get_existing_repetable_rows",
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

    def _create_with_labels(self, block_label, field_label):
        """Crée les lignes d'un bloc dont les libellés viennent de DN tels quels"""
        dossier = self._dossier()
        dossier["champs"][0]["label"] = block_label
        dossier["champs"][0]["rows"][0]["champs"][0]["label"] = field_label
        self.client.post_records.return_value = self._mock_response(201)
        with patch(
            "repetable_processor.get_existing_repetable_rows",
            return_value={},
        ):
            return process_repetables_batch(
                self.client, [dossier], self._table_ids(), self._column_types()
            )

    def test_numbered_block_label_matches_schema_table(self):
        """bloc « 1. Maquettes » -> écrit dans la table créée par le schéma"""
        success, errors = self._create_with_labels("1. Maquettes", "Nom")
        assert (success, errors) == (1, 0)
        assert self.client.post_records.call_args.args[0] == "Demarche_123_maquettes"

    def test_numbered_field_label_matches_schema_column(self):
        """champ « 2) Nom » -> valeur dans la colonne `nom` créée par le schéma"""
        success, errors = self._create_with_labels("Maquettes", "2) Nom")
        assert (success, errors) == (1, 0)
        assert self.client.post_records.call_args.args[1] == [
            {"fields": self._expected_record()}
        ]

    def test_update_batch_records(self):
        """ligne existante -> PATCH lot avec les ids trouvés"""
        existing_rows = {"123:row_1": 42}
        self.client.patch_records.return_value = self._mock_response(200)
        with (
            patch(
                "repetable_processor.get_existing_repetable_rows",
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
        existing_rows = {"123:row_1": 42}
        self.client.patch_records.side_effect = [
            self._mock_response(400),
            self._mock_response(200),
        ]
        with (
            patch(
                "repetable_processor.get_existing_repetable_rows",
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
                "repetable_processor.get_existing_repetable_rows",
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
                "repetable_processor.get_existing_repetable_rows",
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

    def _created_response(self, records):
        response = self._mock_response(201)
        response.json.return_value = {"records": records}
        return response

    def test_existing_rows_cache_skips_refetch(self):
        """existing_rows_cache fourni -> pas de GET de la table"""
        self.client.patch_records.return_value = self._mock_response(200)
        with patch(
            "repetable_processor.get_existing_repetable_rows"
        ) as mock_fetch:
            success, errors = process_repetables_batch(
                self.client,
                [self._dossier()],
                self._table_ids(),
                self._column_types(),
                existing_rows_cache={"maquettes": {"123:row_1": 42}},
            )
        assert (success, errors) == (1, 0)
        mock_fetch.assert_not_called()
        assert self.client.patch_records.call_args.args[1] == [
            {"id": 42, "fields": self._expected_record()}
        ]

    def test_create_updates_cache_in_place(self):
        """création réussie -> le dict de l'appelant reçoit le nouvel id,
        et search_keys n'est pas envoyé à Grist"""
        self.client.post_records.return_value = self._created_response([{"id": 99}])
        shared_cache = {}
        with patch(
            "repetable_processor.get_existing_repetable_rows"
        ) as mock_fetch:
            success, errors = process_repetables_batch(
                self.client,
                [self._dossier()],
                self._table_ids(),
                self._column_types(),
                existing_rows_cache={"maquettes": shared_cache},
            )
        assert (success, errors) == (1, 0)
        mock_fetch.assert_not_called()
        assert self.client.post_records.call_args.args[1] == [
            {"fields": self._expected_record()}
        ]
        assert shared_cache == {"123:row_1": 99}

    def test_create_ids_count_mismatch_reloads_cache(self):
        """nombre d'IDs reçus != lignes envoyées -> pas d'appariement deviné,
        rechargement de la table dans le dict partagé"""
        self.client.post_records.return_value = self._created_response([])
        shared_cache = {"autre_cle": 1}
        with patch(
            "repetable_processor.get_existing_repetable_rows",
            return_value={"row_1": 77},
        ) as mock_fetch:
            process_repetables_batch(
                self.client,
                [self._dossier()],
                self._table_ids(),
                self._column_types(),
                existing_rows_cache={"maquettes": shared_cache},
            )
        mock_fetch.assert_called_once_with(self.client, "Demarche_123_maquettes")
        assert shared_cache == {"autre_cle": 1, "row_1": 77}

    def test_reload_read_error_propagates_and_keeps_cache(self):
        """rechargement après création en échec de lecture -> GristReadError
        propagée, clés déjà connues conservées"""
        self.client.post_records.return_value = self._created_response([])
        shared_cache = {"autre_cle": 1}
        response = self._mock_response(400)
        response.json.return_value = {"error": "[Sandbox] MemoryError"}
        with patch(
            "repetable_processor.get_existing_repetable_rows",
            side_effect=GristReadError("Demarche_123_maquettes", response),
        ):
            with pytest.raises(GristReadError):
                process_repetables_batch(
                    self.client,
                    [self._dossier()],
                    self._table_ids(),
                    self._column_types(),
                    existing_rows_cache={"maquettes": shared_cache},
                )
        assert shared_cache == {"autre_cle": 1}

    def test_create_missing_id_reloads_cache(self):
        """ID absent dans la réponse -> rechargement, pas d'ID None dans le cache"""
        self.client.post_records.return_value = self._created_response([{}])
        shared_cache = {}
        with patch(
            "repetable_processor.get_existing_repetable_rows",
            return_value={},
        ) as mock_fetch:
            process_repetables_batch(
                self.client,
                [self._dossier()],
                self._table_ids(),
                self._column_types(),
                existing_rows_cache={"maquettes": shared_cache},
            )
        mock_fetch.assert_called_once()
        assert None not in shared_cache.values()

    def test_auto_fix_success_updates_cache(self):
        """création via auto-fix -> le cache reçoit aussi les nouveaux IDs"""
        self.client.post_records.return_value = self._mock_response(
            400, text="Invalid column"
        )
        shared_cache = {}
        with patch(
            "repetable_processor.auto_fix_missing_columns_optimized",
            return_value=(True, self._created_response([{"id": 5}])),
        ):
            success, errors = process_repetables_batch(
                self.client,
                [self._dossier()],
                self._table_ids(),
                self._column_types(),
                existing_rows_cache={"maquettes": shared_cache},
            )
        assert (success, errors) == (1, 0)
        assert shared_cache["123:row_1"] == 5

    def test_same_row_id_in_another_dossier_is_created_not_updated(self):
        """dossier 456 avec le même id de ligne que le dossier 123 déjà créé
        -> création, pas de MAJ (la ligne du dossier 123 n'est pas écrasée)"""
        shared_cache = {"123:row_1": 99}
        self.client.post_records.return_value = self._created_response([{"id": 100}])
        other_dossier = self._dossier()
        other_dossier["number"] = 456
        success, errors = process_repetables_batch(
            self.client,
            [other_dossier],
            self._table_ids(),
            self._column_types(),
            existing_rows_cache={"maquettes": shared_cache},
        )
        assert (success, errors) == (1, 0)
        self.client.patch_records.assert_not_called()
        self.client.post_records.assert_called_once()
        assert shared_cache == {"123:row_1": 99, "456:row_1": 100}

    def test_resync_matches_rows_preloaded_from_grist(self):
        """resynchro : ligne relue depuis Grist (sans block_label, numéro en
        float) -> MAJ de cette ligne, pas de nouvelle création"""
        grist_rows = MagicMock()
        grist_rows.status_code = 200
        grist_rows.json.return_value = {
            "records": [
                {"id": 42, "fields": {"dossier_number": 123.0, "block_row_id": "row_1"}}
            ]
        }
        self.client.get_records.return_value = grist_rows
        cache = {
            "maquettes": get_existing_repetable_rows(
                self.client, "Demarche_123_maquettes"
            )
        }
        self.client.patch_records.return_value = self._mock_response(200)
        success, errors = process_repetables_batch(
            self.client,
            [self._dossier()],
            self._table_ids(),
            self._column_types(),
            existing_rows_cache=cache,
        )
        assert (success, errors) == (1, 0)
        self.client.post_records.assert_not_called()
        assert self.client.patch_records.call_args.args[1] == [
            {"id": 42, "fields": self._expected_record()}
        ]

    def test_resync_matches_geo_rows(self):
        """resynchro d'une ligne avec géométrie -> MAJ via (dossier, row_id_geoN)"""
        dossier = self._dossier()
        dossier["champs"][0]["rows"][0]["champs"] = [
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
        ]
        column_types = {
            "maquettes": {
                "columns": [
                    {"id": "carte", "type": "Text"},
                    {"id": "geo_id", "type": "Text"},
                ]
            }
        }
        self.client.patch_records.return_value = self._mock_response(200)
        success, errors = process_repetables_batch(
            self.client,
            [dossier],
            self._table_ids(),
            column_types,
            existing_rows_cache={"maquettes": {"123:row_1_geo1": 7}},
        )
        assert (success, errors) == (1, 0)
        self.client.post_records.assert_not_called()
        patched = self.client.patch_records.call_args.args[1]
        assert patched[0]["id"] == 7
        assert patched[0]["fields"]["block_row_id"] == "row_1_geo1"


class TestProcessRepetablesBatchPurge:
    """Suppression des lignes de blocs que DN ne renvoie plus"""

    def setup_method(self):
        self.client = MagicMock()
        self.client.doc_id = "doc1"
        ok = MagicMock()
        ok.status_code = 200
        self.client.patch_records.return_value = ok
        self.client.delete_records.return_value = ok
        created = MagicMock()
        created.status_code = 201
        created.json.return_value = {"records": [{"id": 100}]}
        self.client.post_records.return_value = created

    @staticmethod
    def _row(row_id, nom="x"):
        return {
            "id": row_id,
            "champs": [{"__typename": "TextChamp", "label": "Nom", "stringValue": nom}],
        }

    def _dossier(self, rows, number=123, annotation_rows=None):
        dossier = {
            "number": number,
            "champs": [
                {
                    "__typename": "RepetitionChamp",
                    "id": "bloc_1",
                    "champDescriptorId": "desc_bloc",
                    "label": "Maquettes",
                    "rows": rows,
                }
            ],
            "annotations": [],
        }
        if annotation_rows is not None:
            dossier["annotations"] = [
                {
                    "__typename": "RepetitionChamp",
                    "id": "bloc_a",
                    "label": "Suivi",
                    "rows": annotation_rows,
                }
            ]
        return dossier

    @staticmethod
    def _table_ids():
        return {
            "maquettes": "Demarche_123_maquettes",
            "annotation_suivi": "Demarche_123_annotation_suivi",
        }

    @staticmethod
    def _column_types():
        columns = {"columns": [{"id": "nom", "type": "Text"}]}
        return {"maquettes": columns, "annotation_suivi": columns}

    def _run(self, dossiers, cache, **kwargs):
        return process_repetables_batch(
            self.client,
            dossiers,
            self._table_ids(),
            self._column_types(),
            existing_rows_cache=cache,
            **kwargs,
        )

    def _deleted(self, table_id):
        return [
            c.args[1]
            for c in self.client.delete_records.call_args_list
            if c.args[0] == table_id
        ]

    def test_deleted_row_is_removed(self):
        """3 lignes dans Grist, r2 supprimée dans DN, r4 ajoutée -> MAJ r1/r3,
        création r4, suppression de r2 et retrait du cache"""
        cache = {"maquettes": {"123:r1": 1, "123:r2": 2, "123:r3": 3}}
        dossier = self._dossier([self._row("r1"), self._row("r3"), self._row("r4")])
        success, errors = self._run([dossier], cache)
        assert errors == 0
        patched = [r["id"] for r in self.client.patch_records.call_args.args[1]]
        assert patched == [1, 3]
        assert self._deleted("Demarche_123_maquettes") == [[2]]
        assert cache["maquettes"] == {"123:r1": 1, "123:r3": 3, "123:r4": 100}

    def test_emptied_block_is_purged(self):
        """bloc entièrement vidé dans DN -> toutes ses lignes supprimées"""
        cache = {"maquettes": {"123:r1": 1, "123:r2": 2}}
        self._run([self._dossier([])], cache)
        assert self._deleted("Demarche_123_maquettes") == [[1, 2]]
        assert cache["maquettes"] == {}

    def test_other_dossiers_rows_are_untouched(self):
        """lignes d'un dossier absent du lot -> jamais supprimées"""
        cache = {"maquettes": {"123:r1": 1, "456:r1": 2}}
        self._run([self._dossier([self._row("r1")])], cache)
        self.client.delete_records.assert_not_called()

    def test_extraction_error_blocks_purge(self):
        """erreur d'extraction d'une ligne -> aucune purge pour ce dossier"""
        cache = {"maquettes": {"123:r1": 1, "123:r2": 2}}
        broken_row = {"id": "r1", "champs": [{"__typename": "TextChamp"}]}
        _, errors = self._run([self._dossier([broken_row])], cache)
        assert errors == 1
        self.client.delete_records.assert_not_called()

    def test_problematic_block_is_never_purged(self):
        """bloc filtré par problematic_ids -> pas de purge de sa table"""
        cache = {"maquettes": {"123:r1": 1}}
        self._run([self._dossier([])], cache, problematic_ids={"desc_bloc"})
        self.client.delete_records.assert_not_called()

    def test_annotations_not_returned_blocks_annotation_purge(self):
        """annotations absentes de la réponse DN -> pas de purge des blocs
        d'annotations, purge des blocs de champs maintenue"""
        cache = {
            "maquettes": {"123:r1": 1, "123:r2": 2},
            "annotation_suivi": {"123:a1": 10},
        }
        dossier = self._dossier([self._row("r1")])
        del dossier["annotations"]
        self._run([dossier], cache)
        assert self._deleted("Demarche_123_maquettes") == [[2]]
        assert self._deleted("Demarche_123_annotation_suivi") == []

    def test_annotation_block_row_is_purged(self):
        """ligne supprimée dans un bloc d'annotations -> supprimée"""
        cache = {
            "maquettes": {"123:r1": 1},
            "annotation_suivi": {"123:a1": 10, "123:a2": 11},
        }
        dossier = self._dossier([self._row("r1")], annotation_rows=[self._row("a1")])
        self._run([dossier], cache)
        assert self._deleted("Demarche_123_annotation_suivi") == [[11]]
        assert self._deleted("Demarche_123_maquettes") == []

    def test_removed_geo_area_is_purged(self):
        """zone géo retirée d'une ligne -> sa ligne _geoN est supprimée"""
        cache = {"maquettes": {"123:r1_geo1": 1, "123:r1_geo2": 2}}
        row = {
            "id": "r1",
            "champs": [
                {
                    "__typename": "CarteChamp",
                    "label": "Carte",
                    "geoAreas": [{"id": "g1", "description": "A"}],
                }
            ],
        }
        self._run([self._dossier([row])], cache)
        assert self._deleted("Demarche_123_maquettes") == [[2]]

    def test_delete_failure_counts_errors_and_keeps_cache(self):
        """suppression refusée -> erreurs comptées, cache inchangé"""
        refused = MagicMock()
        refused.status_code = 500
        self.client.delete_records.return_value = refused
        cache = {"maquettes": {"123:r1": 1, "123:r2": 2}}
        _, errors = self._run([self._dossier([self._row("r1")])], cache)
        assert errors == 1
        assert cache["maquettes"] == {"123:r1": 1, "123:r2": 2}

    def test_float_dossier_number_in_cache_is_purged(self):
        """numéro relu en float depuis Grist -> même dossier, purge appliquée"""
        cache = {"maquettes": {"123:r1": 1, "123:r2": 2}}
        self._run([self._dossier([self._row("r1")], number=123.0)], cache)
        assert self._deleted("Demarche_123_maquettes") == [[2]]

    def test_delete_is_batched(self, monkeypatch):
        """suppressions envoyées par lots de DELETE_BATCH_SIZE"""
        monkeypatch.setattr("repetable_processor.DELETE_BATCH_SIZE", 2)
        cache = {"maquettes": {f"123:r{i}": i for i in range(5)}}
        self._run([self._dossier([])], cache)
        assert self._deleted("Demarche_123_maquettes") == [[0, 1], [2, 3], [4]]
