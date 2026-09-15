"""Test d'intégration de la pipeline de sync complète (périmètre Grist).

Exécute réellement `process_demarche_for_grist_optimized` avec :
- la couche DN mockée (schéma, liste des dossiers, dossiers complets) ;
- le transport HTTP Grist mocké au seam `grist.client.requests` (serveur Grist factice) ;
- les sous-tâches `sync_instructeurs`, `sync_labels_for_demarche`, `check_deleted_dossiers`
  mockées ; `IdColumnHider` réel.

Aucun service externe (DN, Grist, DB) n'est requis.
"""

import json
from contextlib import ExitStack
from unittest.mock import patch
from urllib.parse import urlparse

import requests

import grist.client as grist_client_module
import grist_processor_working_all as gpa
import schema_utils
from grist.client import GristClient

BASE_URL = "https://grist.test"
DOC_ID = "doc123"
DEMARCHE_NUMBER = 12345


def build_response(payload, status=200):
    """Fabrique une vraie `requests.Response` avec le payload JSON voulu."""
    resp = requests.Response()
    resp.status_code = status
    resp._content = json.dumps(payload).encode("utf-8")
    resp.headers["Content-Type"] = "application/json"
    return resp


class FakeGristServer:
    """Mini serveur Grist en mémoire : tables + colonnes, trace de tous les appels.

    `initial_records` permet de pré-remplir une table (ex: Sync_metadata) avec
    des enregistrements retournés lors du premier GET records de cette table.
    Format : {table_id: [{champ: valeur, ...}, ...]}
    """

    def __init__(self, initial_records=None):
        self.tables = {}
        self.calls = []
        self._initial_records = initial_records or {}
        self._records_sent = set()
        self._add_initial_tables()

    def _add_initial_tables(self):
        self.tables["Demarche_12345_dossiers"] = {
            "id": "Id",
            "manualSort": "ManualSortPos",
            "dossier_id": "Text",
            "dossier_number": "Int",
            "state": "Text",
        }
        self.tables["Demarche_12345_champs"] = {
            "id": "Id",
            "dossier_number": "Int",
            "champ_id": "Text",
        }

    def handle(self, method, url, payload=None):
        method = method.upper()
        self.calls.append(
            {"method": method, "path": urlparse(url).path, "json": payload}
        )
        parts = [p for p in urlparse(url).path.split("/") if p]
        return self._route(method, parts, payload)

    def _route(self, method, parts, payload):
        if method == "GET" and parts == ["docs", DOC_ID]:
            return build_response({"name": "Doc de test", "id": DOC_ID})

        if parts[:3] != ["docs", DOC_ID, "tables"]:
            raise AssertionError(f"Requête non prévue : {method} {parts}")

        if len(parts) == 3:
            if method == "GET":
                return build_response({"tables": [{"id": tid} for tid in self.tables]})
            if method == "POST":
                for table in payload["tables"]:
                    self.tables[table["id"]] = {
                        col["id"]: col.get("type", "Text")
                        for col in table["columns"]
                    }
                return build_response(
                    {"tables": [{"id": t["id"]} for t in payload["tables"]]}
                )
            raise AssertionError(f"Requête non prévue : {method} {parts}")

        table_id = parts[3]

        if method == "GET" and parts[4] == "columns":
            return build_response(
                {
                    "columns": [
                        {"id": cid, "type": ctype}
                        for cid, ctype in self.tables.get(table_id, {}).items()
                    ]
                }
            )

        if method == "GET" and parts[4] == "records":
            if parts[3] in self._initial_records and parts[3] not in self._records_sent:
                self._records_sent.add(parts[3])
                records = self._initial_records[parts[3]]
                return build_response(
                    {
                        "records": [
                            {"id": i + 1, "fields": r}
                            for i, r in enumerate(records)
                        ]
                    }
                )
            return build_response({"records": []})

        if method == "POST" and len(parts) == 4:
            for table in payload["tables"]:
                self.tables[table["id"]] = {
                    col["id"]: col.get("type", "Text") for col in table["columns"]
                }
            return build_response({"tables": [{"id": t["id"]} for t in payload["tables"]]})

        if method == "POST" and parts[4] == "columns":
            for col in payload["columns"]:
                self.tables.setdefault(table_id, {})[col["id"]] = col.get("type", "Text")
            return build_response({})

        if method in ("POST", "PATCH") and parts[4] == "records":
            return build_response({"records": []})

        if method == "POST" and parts[4] == "records" and parts[5] == "delete":
            return build_response({})

        raise AssertionError(f"Requête non prévue : {method} {parts}")


def make_schema():
    """Schéma DS minimal (2 champs textes : 1 champ, 1 annotation)."""
    return {
        "title": "Démarche test",
        "activeRevision": {
            "champDescriptors": [
                {
                    "__typename": "TextChampDescriptor",
                    "id": "desc_objet",
                    "type": "text",
                    "label": "Objet de la demande",
                    "description": "",
                    "required": False,
                }
            ],
            "annotationDescriptors": [
                {
                    "__typename": "TextChampDescriptor",
                    "id": "desc_annote",
                    "type": "text",
                    "label": "Annotation interne",
                    "description": "",
                    "required": False,
                }
            ],
        },
    }


def make_dossier_brief(number):
    """Entrée de liste de dossiers (utilisée pour la constitution des lots)."""
    return {"number": number, "state": "accepte"}


def make_dossier(number):
    """Dossier DS complet (format réel de l'API)."""
    return {
        "id": f"dossier_{number}",
        "number": number,
        "state": "accepte",
        "dateDepot": "2024-01-01T00:00:00Z",
        "dateDerniereModification": "2024-01-01T00:00:00Z",
        "dateDerniereModificationChamps": None,
        "dateDerniereModificationAnnotations": None,
        "datePassageEnConstruction": None,
        "datePassageEnInstruction": None,
        "dateExpiration": None,
        "dateTraitement": None,
        "dateSuppressionParUsager": None,
        "dateAccuseLectureAgreement": None,
        "labels": [],
        "champs": [
            {
                "__typename": "TextChamp",
                "id": "id_objet",
                "champDescriptorId": "desc_objet",
                "label": "Objet de la demande",
                "stringValue": "Projet X",
                "updatedAt": "2024-01-01T00:00:00Z",
                "prefilled": False,
            }
        ],
        "annotations": [
            {
                "__typename": "TextChamp",
                "id": "id_annot",
                "champDescriptorId": "desc_annote",
                "label": "Annotation interne",
                "stringValue": "note",
                "updatedAt": "2024-01-01T00:00:00Z",
                "prefilled": False,
            }
        ],
        "avis": [
            {
                "id": "avis_1",
                "question": "Question ?",
                "reponse": "Oui",
                "claimant": {"email": "instructeur@test.fr"},
                "expert": {"email": "expert@test.fr"},
                "dateQuestion": "2024-01-02T00:00:00Z",
                "dateReponse": "2024-01-03T00:00:00Z",
            }
        ],
        "usager": {"email": "test@test.fr"},
        "demandeur": None,
        "traitements": [],
        "instructeurs": [{"email": "inst@test.fr"}],
    }


class TestSyncPipelineGrist:
    def test_process_demarche_pipeline_complete_writes_to_grist(self):
        server = FakeGristServer()
        client = GristClient(BASE_URL, "api-key", DOC_ID)

        with ExitStack() as stack:
            for method in ("get", "post", "patch"):
                stack.enter_context(
                    patch.object(
                        grist_client_module.requests,
                        method,
                        side_effect=lambda *args, method=method, **kwargs: server.handle(
                            method, args[0], kwargs.get("json")
                        ),
                    )
                )
            stack.enter_context(
                patch.object(gpa, "get_optimized_schema", return_value=make_schema())
            )
            stack.enter_context(
                patch.object(
                    gpa,
                    "get_demarche_dossiers_filtered",
                    return_value=[make_dossier_brief(1)],
                )
            )
            stack.enter_context(
                patch.object(gpa, "get_dossier", side_effect=make_dossier)
            )
            stack.enter_context(
                patch.object(schema_utils, "detect_demandeur_type", return_value=None)
            )
            mock_instructeurs = stack.enter_context(
                patch.object(gpa, "sync_instructeurs")
            )
            mock_labels = stack.enter_context(
                patch.object(gpa, "sync_labels_for_demarche")
            )
            mock_deleted = stack.enter_context(
                patch.object(
                    gpa,
                    "check_deleted_dossiers",
                    return_value={"newly_marked": 0},
                )
            )

            result = gpa.process_demarche_for_grist_optimized(
                client,
                DEMARCHE_NUMBER,
                parallel=False,
                batch_size=100,
                api_filters={"statuts": ["accepte"]},
            )

        assert result is True

        # Le document Grist a été vérifié
        assert any(
            call["method"] == "GET" and call["path"] == f"/docs/{DOC_ID}"
            for call in server.calls
        )

        # Toutes les tables attendues existent
        assert "Demarche_12345_dossiers" in server.tables
        assert "Demarche_12345_champs" in server.tables
        assert "Demarche_12345_annotations" in server.tables
        assert "Demarche_12345_demandeurs" in server.tables
        assert "Demarche_12345_instructeurs" in server.tables
        assert "Sync_metadata" in server.tables
        assert "Demarche_12345_avis" in server.tables

        # Colonnes ajoutées via add_columns (évolution de schéma + id d'annotation)
        assert "suivi_par" in server.tables["Demarche_12345_dossiers"]
        assert "objet_de_la_demande" in server.tables["Demarche_12345_champs"]
        assert "annotation_interne" in server.tables["Demarche_12345_annotations"]
        assert "annotation_interne_id" in server.tables["Demarche_12345_annotations"]

        # Upserts : un POST de création par table, avec les bons payloads
        records_posts = {
            table: [
                call["json"]["records"]
                for call in server.calls
                if call["method"] == "POST"
                and call["path"] == f"/docs/{DOC_ID}/tables/{table}/records"
            ]
            for table in server.tables
        }

        dossier_fields = records_posts["Demarche_12345_dossiers"][0][0]["fields"]
        assert len(records_posts["Demarche_12345_dossiers"]) == 1
        assert dossier_fields["dossier_number"] == 1
        assert dossier_fields["suivi_par"] == "inst@test.fr"
        assert dossier_fields["state"] == "accepte"

        champ_fields = records_posts["Demarche_12345_champs"][0][0]["fields"]
        assert len(records_posts["Demarche_12345_champs"]) == 1
        assert champ_fields["dossier_number"] == 1
        assert champ_fields["objet_de_la_demande"] == "Projet X"

        annotation_fields = records_posts["Demarche_12345_annotations"][0][0]["fields"]
        assert len(records_posts["Demarche_12345_annotations"]) == 1
        assert annotation_fields["dossier_number"] == 1
        assert annotation_fields["annotation_interne"] == "note"
        assert annotation_fields["annotation_interne_id"] == "id_annot"

        avis_fields = records_posts["Demarche_12345_avis"][0][0]["fields"]
        assert len(records_posts["Demarche_12345_avis"]) == 1
        assert avis_fields["dossier_number"] == 1
        assert avis_fields["avis_id"] == "avis_1"
        assert avis_fields["question"] == "Question ?"
        assert avis_fields["expert_email"] == "expert@test.fr"

        # Sync_metadata enregistrée en succès
        sync_posts = [
            call["json"]
            for call in server.calls
            if call["method"] == "POST"
            and call["path"] == f"/docs/{DOC_ID}/tables/Sync_metadata/records"
        ]
        assert len(sync_posts) == 1
        sync_fields = sync_posts[0]["records"][0]["fields"]
        assert sync_fields["demarche_number"] == DEMARCHE_NUMBER
        assert sync_fields["last_sync_status"] == "success"

        # Tâches de niveau démarche : instructeurs + suppression actives,
        # labels absents (sync complète), IdColumnHider exécuté
        mock_instructeurs.assert_called_once()
        mock_deleted.assert_called_once()
        mock_labels.assert_not_called()
        for table in [
            "_grist_Tables",
            "_grist_Tables_column",
            "_grist_Views_section",
            "_grist_Views_section_field",
        ]:
            assert any(
                call["method"] == "GET"
                and call["path"] == f"/docs/{DOC_ID}/tables/{table}/records"
                for call in server.calls
            )

    def test_filter_change_forces_full_sync(self):
        """Quand les filtres changent entre deux syncs, le cursor
        `updated_since` doit être ignoré (sync complète) pour ne pas manquer
        les dossiers correspondant aux nouveaux critères.

        Scénario : la 1ère sync a tourné avec des filtres A (cursor positionné
        + hash stocké). On relance avec des filtres B différents. Le delta
        utilisant `updated_since` ne verrait que les dossiers modifiés et
        ignorerait les dossiers nouvellement éligibles aux filtres B.

        Régression : sans détection du changement de filtres, l'appel à
        `get_demarche_dossiers_filtered` reçoit encore `updated_since`, donc
        le test échoue.
        """
        server = FakeGristServer(
            initial_records={
                "Sync_metadata": [
                    {
                        "demarche_number": DEMARCHE_NUMBER,
                        "updated_since_cursor": "2024-06-01T00:00:00Z",
                        "deleted_since_cursor": "2024-06-01T00:00:00Z",
                        "filters_hash": "hash_anciens_filtres",
                        "force_full_sync": False,
                    }
                ]
            }
        )
        client = GristClient(BASE_URL, "api-key", DOC_ID)

        with ExitStack() as stack:
            for method in ("get", "post", "patch"):
                stack.enter_context(
                    patch.object(
                        grist_client_module.requests,
                        method,
                        side_effect=lambda *args, method=method, **kwargs: server.handle(
                            method, args[0], kwargs.get("json")
                        ),
                    )
                )
            stack.enter_context(
                patch.object(gpa, "get_optimized_schema", return_value=make_schema())
            )
            mock_fetch = stack.enter_context(
                patch.object(
                    gpa,
                    "get_demarche_dossiers_filtered",
                    return_value=[make_dossier_brief(1)],
                )
            )
            stack.enter_context(
                patch.object(gpa, "get_dossier", side_effect=make_dossier)
            )
            stack.enter_context(
                patch.object(schema_utils, "detect_demandeur_type", return_value=None)
            )
            stack.enter_context(patch.object(gpa, "sync_instructeurs"))
            stack.enter_context(patch.object(gpa, "sync_labels_for_demarche"))
            stack.enter_context(
                patch.object(
                    gpa,
                    "check_deleted_dossiers",
                    return_value={"newly_marked": 0},
                )
            )

            result = gpa.process_demarche_for_grist_optimized(
                client,
                DEMARCHE_NUMBER,
                parallel=False,
                batch_size=100,
                # Filtres DIFFÉRENTS de ceux stockés dans Sync_metadata
                api_filters={"statuts": ["en_instruction"]},
            )

        assert result is True

        # Le changement de filtres doit forcer une sync complète : le cursor
        # updated_since est ignoré lors de l'appel à la couche DN.
        call_kwargs = mock_fetch.call_args.kwargs
        assert call_kwargs.get("updated_since") is None, (
            "Les filtres ont changé mais le cursor updated_since a été utilisé "
            "→ les dossiers correspondant aux nouveaux filtres seraient ignorés"
        )

