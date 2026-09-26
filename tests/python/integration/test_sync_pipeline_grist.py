"""Test d'intégration de la pipeline de sync complète (périmètre Grist).

Ces tests exécutent réellement `process_demarche_for_grist_optimized` et
**n'affirment que l'état final du document Grist** : quel que soit le découpage
technique retenu (pagination, lots, requêtes), les mêmes dossiers doivent se
retrouver dans le document, avec les mêmes champs.

Le transport HTTP Grist est intercepté au seam `grist.client.requests` et servi
par `FakeGristServer`, un serveur factice **persistant** : les écritures sont
conservées, l'état final est donc observable.

La couche DN est branchée sur `FakeDemarchesServer`, un faux serveur GraphQL DN
avec pagination par curseurs, via le seam `dn.client.get_session_with_retries` :
la vraie pagination DS est donc traversée. Ce faux serveur sert un dossier
"résumé" ou "détaillé" selon la query reçue, si bien qu'une requête qui
abandonnerait les détails se verrait dans l'état final Grist.

Sont mockés, pour isoler le périmètre : `get_optimized_schema` (schéma DS),
`sync_instructeurs`, `sync_labels_for_demarche`, `check_deleted_dossiers`,
`detect_demandeur_type` et `IdColumnHider` (dernière tâche de niveau démarche,
dont on vérifie seulement qu'elle est exécutée).

Aucun service externe (DN, Grist, DB) n'est requis.
"""

import json
import os
import re
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlparse

import requests

import dn.client as dn_client_module
import grist.client as grist_client_module
import grist_processor_working_all as gpa
import schema_utils
from grist.client import GristClient
from sync.filters import build_filters_cache_key

BASE_URL = "https://grist.test"
DOC_ID = "doc123"
DEMARCHE_NUMBER = 12345
DOSSIERS_TABLE = "Demarche_12345_dossiers"
CHAMPS_TABLE = "Demarche_12345_champs"
ANNOTATIONS_TABLE = "Demarche_12345_annotations"
AVIS_TABLE = "Demarche_12345_avis"
SYNC_METADATA_TABLE = "Sync_metadata"

# `.env` est chargé au import de `dn.client` : les variables de filtre sont
# neutralisées par défaut pour que le `.env` du poste n'altère pas les tests.
# `run_pipeline(filters=...)` permet de surcharger une partie de ces filtres.
FILTRES_VIDES = {
    "DATE_DEPOT_DEBUT": "",
    "DATE_DEPOT_FIN": "",
    "STATUTS_DOSSIERS": "",
    "GROUPES_INSTRUCTEURS": "",
}


def build_response(payload, status=200):
    """Fabrique une vraie `requests.Response` avec le payload JSON voulu."""
    resp = requests.Response()
    resp.status_code = status
    resp._content = json.dumps(payload).encode("utf-8")
    resp.headers["Content-Type"] = "application/json"
    return resp


class FakeGristServer:
    """Mini serveur Grist en mémoire : tables, colonnes et **enregistrements**.

    Les POST/PATCH records sont conservés : `rows()` et `column()` exposent
    l'état final du document, ce qui permet d'affirmer qu'un dossier a bien
    été écrit (ou mis à jour) plutôt que de supposer que le code le fait.

    `initial_records` permet de pré-remplir une table (ex: un dossier déjà
    synchronisé, une ligne Sync_metadata).
    Format : {table_id: [{champ: valeur, ...}, ...]}
    """

    def __init__(self, initial_records=None):
        self.tables = {}
        self.store = {}
        self._next_id = {}
        self._add_initial_tables()
        for table_id, records in (initial_records or {}).items():
            for fields in records:
                self._insert(table_id, fields)

    def _add_initial_tables(self):
        self.tables[DOSSIERS_TABLE] = {
            "id": "Id",
            "manualSort": "ManualSortPos",
            "dossier_id": "Text",
            "dossier_number": "Int",
            "state": "Text",
        }
        self.tables[CHAMPS_TABLE] = {
            "id": "Id",
            "dossier_number": "Int",
            "champ_id": "Text",
        }

    def _insert(self, table_id, fields):
        next_id = self._next_id.get(table_id, 0) + 1
        self._next_id[table_id] = next_id
        self.store.setdefault(table_id, {})[next_id] = dict(fields)
        return next_id

    def rows(self, table_id):
        """État final d'une table : champs des enregistrements, par ordre d'id."""
        return [dict(fields) for fields in self.store.get(table_id, {}).values()]

    def column(self, table_id, column_id):
        """Valeurs d'une colonne pour tous les enregistrements de la table."""
        return [
            fields[column_id] for fields in self.rows(table_id) if column_id in fields
        ]

    def metadata(self, demarche_number):
        """Ligne Sync_metadata d'une démarche, ou None si absente."""
        for fields in self.rows(SYNC_METADATA_TABLE):
            if str(fields.get("demarche_number")) == str(demarche_number):
                return fields
        return None

    def handle(self, method, url, payload=None):
        method = method.upper()
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

        if method == "POST" and parts[4:] == ["records", "delete"]:
            for record_id in payload or []:
                self.store.get(table_id, {}).pop(record_id, None)
            return build_response({})

        if method == "GET" and parts[4:] == ["records"]:
            return build_response(
                {
                    "records": [
                        {"id": record_id, "fields": dict(fields)}
                        for record_id, fields in sorted(
                            self.store.get(table_id, {}).items()
                        )
                    ]
                }
            )

        if method == "POST" and parts[4:] == ["records"]:
            return build_response(
                {
                    "records": [
                        {"id": self._insert(table_id, record["fields"])}
                        for record in payload["records"]
                    ]
                }
            )

        if method == "PATCH" and parts[4:] == ["records"]:
            for record in payload["records"]:
                stored = self.store.get(table_id, {}).get(record["id"])
                if stored is not None:
                    stored.update(record["fields"])
            return build_response(
                {"records": [{"id": record["id"]} for record in payload["records"]]}
            )

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


def make_dossier(number, **overrides):
    """Dossier DS complet (format réel de l'API).

    `overrides` permet de faire varier un champ (statut, date de dépôt,
    groupe instructeur) dossier par dossier.
    """
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
                "id": f"avis_{number}",
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
        **overrides,
    }


def dossiers_de_test(nombre):
    """Les `nombre` premiers dossiers, numérotés de 1 à `nombre`."""
    return [make_dossier(number) for number in range(1, nombre + 1)]


MARQUEUR_DETAIL = "champs"
"""La query de résumé ne demande pas les `champs`, le fragment détaillé si."""

RESUME_CLES = (
    "id",
    "number",
    "state",
    "archived",
    "prefilled",
    "dateDepot",
    "dateDerniereModification",
    "datePassageEnConstruction",
    "datePassageEnInstruction",
    "dateTraitement",
    "usager",
    "groupeInstructeur",
    "demandeur",
    "labels",
)


class FakeDemarchesServer:
    """Faux serveur GraphQL DN : sert la liste paginée des dossiers et, tant
    qu'elle est appelée, le détail unitaire.

    Les curseurs sont opaques (`cursor:<décalage>`) : le client doit les
    reprendre tels quels. La forme des dossiers servie dépend de la query
    reçue (résumé ou détail détaillé), si bien qu'une query paginée qui
    abandonnerait les détails se voit dans l'état final Grist.

    `page_en_erreur` (optionnel) fait répondre la page de ce numéro par une
    erreur GraphQL, comme une API DN qui tombe en cours de parcours.
    """

    def __init__(self, dossiers, page_en_erreur=None):
        self.dossiers = dossiers
        self.page_en_erreur = page_en_erreur

    def _offset(self, cursor):
        prefixe, _, valeur = str(cursor).partition(":")
        assert prefixe == "cursor" and valeur.isdigit(), f"Curseur inattendu : {cursor!r}"
        return int(valeur)

    def _page_size(self, query, variables):
        if variables.get("first") is not None:
            return int(variables["first"])
        trouve = re.search(r"first:\s*(\d+)", query)
        return int(trouve.group(1)) if trouve else 100

    def _filtres_serveur(self, variables):
        dossiers = self.dossiers
        updated_since = variables.get("updatedSince")
        if updated_since:
            dossiers = [
                d
                for d in dossiers
                if d["dateDerniereModification"] > updated_since
            ]
        created_since = variables.get("createdSince")
        if created_since:
            dossiers = [d for d in dossiers if d["dateDepot"] > created_since]
        return dossiers

    def _resume(self, dossier):
        return {cle: dossier.get(cle) for cle in RESUME_CLES}

    def handle(self, query, variables):
        if "dossiers(" in query:
            return self._liste_paginee(query, variables)
        assert "dossier(number:" in query, f"Query DN non prévue : {query[:120]}"
        return self._dossier_unitaire(query, variables)

    def _dossier_unitaire(self, query, variables):
        number = variables.get("dossierNumber")
        dossier = next((d for d in self.dossiers if d["number"] == number), None)
        return build_response(
            {"data": {"dossier": dossier if dossier is None else self._forme(query, dossier)}}
        )

    def _liste_paginee(self, query, variables):
        first = self._page_size(query, variables)
        after = variables.get("after", variables.get("afterCursor"))
        dossiers = self._filtres_serveur(variables)
        debut = 0 if after is None else self._offset(after)
        if self.page_en_erreur == debut // max(first, 1) + 1:
            return build_response(
                {"errors": [{"message": "Erreur interne du serveur DN"}]}
            )
        fenetre = dossiers[debut : debut + first]
        suite = debut + len(fenetre) < len(dossiers)
        end_cursor = f"cursor:{debut + len(fenetre)}" if suite else None

        nodes = [self._forme(query, dossier) for dossier in fenetre]
        return build_response(
            {
                "data": {
                    "demarche": {
                        "id": "demarche_1",
                        "number": DEMARCHE_NUMBER,
                        "title": "Démarche test",
                        "dossiers": {
                            "pageInfo": {
                                "hasPreviousPage": debut > 0,
                                "hasNextPage": suite,
                                "startCursor": f"cursor:{debut}",
                                "endCursor": end_cursor,
                            },
                            "nodes": nodes,
                        },
                    }
                }
            }
        )

    def _forme(self, query, dossier):
        return dict(dossier) if MARQUEUR_DETAIL in query else self._resume(dossier)


class FakeDemarchesSession:
    """Session HTTP factice : ne sert que les POST GraphQL de `dn.client`."""

    def __init__(self, server):
        self.server = server

    def post(self, url, **kwargs):
        payload = kwargs.get("json") or {}
        return self.server.handle(
            payload.get("query", ""), payload.get("variables") or {}
        )


def run_pipeline(server, dn_server, filters=None, **pipeline_kwargs):
    """Exécute la pipeline contre `server` et renvoie `(résultat, mocks)`.

    La couche DN réelle est branchée sur `dn_server` (faux serveur GraphQL
    paginé) ; seule la dernière tâche de niveau démarche est observée.

    `filters` surcharge les variables de filtre neutralisées par défaut, afin
    que les tests n dépendent pas du `.env` du poste.
    """
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
            patch.object(dn_client_module, "API_TOKEN", "jeton-de-test")
        )
        stack.enter_context(
            patch.object(
                dn_client_module,
                "get_session_with_retries",
                return_value=FakeDemarchesSession(dn_server),
            )
        )
        stack.enter_context(
            patch.dict(os.environ, {**FILTRES_VIDES, **(filters or {})})
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
        hider = stack.enter_context(patch.object(gpa, "IdColumnHider"))

        result = gpa.process_demarche_for_grist_optimized(
            client,
            DEMARCHE_NUMBER,
            **pipeline_kwargs,
        )

    mocks = SimpleNamespace(hider=hider)
    return result, mocks


class TestSyncPipelineGrist:
    def test_process_demarche_pipeline_complete_writes_to_grist(self):
        """Une sync complète écrit le dossier, ses champs, son annotation, son
        avis et les métadonnées de sync, et crée les tables attendues.
        """
        server = FakeGristServer()
        dn_server = FakeDemarchesServer([make_dossier(1)])

        result, mocks = run_pipeline(server, dn_server, parallel=False)

        assert result is True

        # Toutes les tables attendues existent
        assert DOSSIERS_TABLE in server.tables
        assert CHAMPS_TABLE in server.tables
        assert ANNOTATIONS_TABLE in server.tables
        assert "Demarche_12345_demandeurs" in server.tables
        assert "Demarche_12345_instructeurs" in server.tables
        assert SYNC_METADATA_TABLE in server.tables
        assert AVIS_TABLE in server.tables

        # Colonnes ajoutées via add_columns (évolution de schéma + id d'annotation)
        assert "suivi_par" in server.tables[DOSSIERS_TABLE]
        assert "objet_de_la_demande" in server.tables[CHAMPS_TABLE]
        assert "annotation_interne" in server.tables[ANNOTATIONS_TABLE]
        assert "annotation_interne_id" in server.tables[ANNOTATIONS_TABLE]

        # Le dossier est écrit avec les valeurs de la source
        dossiers = server.rows(DOSSIERS_TABLE)
        assert len(dossiers) == 1
        assert dossiers[0]["dossier_number"] == 1
        assert dossiers[0]["state"] == "accepte"
        assert dossiers[0]["suivi_par"] == "inst@test.fr"

        # Idem pour les champs, annotations et avis rattachés
        champs = server.rows(CHAMPS_TABLE)
        assert len(champs) == 1
        assert champs[0]["dossier_number"] == 1
        assert champs[0]["objet_de_la_demande"] == "Projet X"

        annotations = server.rows(ANNOTATIONS_TABLE)
        assert len(annotations) == 1
        assert annotations[0]["dossier_number"] == 1
        assert annotations[0]["annotation_interne"] == "note"
        assert annotations[0]["annotation_interne_id"] == "id_annot"

        avis = server.rows(AVIS_TABLE)
        assert len(avis) == 1
        assert avis[0]["dossier_number"] == 1
        assert avis[0]["avis_id"] == "avis_1"
        assert avis[0]["question"] == "Question ?"
        assert avis[0]["expert_email"] == "expert@test.fr"

        # Sync_metadata enregistrée en succès
        metadata = server.metadata(DEMARCHE_NUMBER)
        assert metadata["demarche_number"] == DEMARCHE_NUMBER
        assert metadata["last_sync_status"] == "success"

        # Le masquage des colonnes `_id` est toujours exécuté en fin de sync
        mocks.hider.return_value.hide_id_columns.assert_called_once()

    def test_filter_change_forces_full_sync(self):
        """Un changement de filtres doit réintégrer dans le document les dossiers
        que le repère de reprise aurait écartés.

        Scénario : `Sync_metadata` porte un repère `updated_since` et un hash de
        filtres obsolètes. Un dossier déposé avant ce repère n'est pas renvoyé
        par le delta `updatedSince` : il ne doit pas pour autant manquer dans le
        document, sous peine d'être ignoré à jamais.

        Régression : sans détection du changement de filtres, le delta ne verrait
        que le dossier modifié et l'autre resterait absent.
        """
        cursor_initial = "2024-06-01T00:00:00Z"
        server = FakeGristServer(
            initial_records={
                SYNC_METADATA_TABLE: [
                    {
                        "demarche_number": DEMARCHE_NUMBER,
                        "updated_since_cursor": cursor_initial,
                        "deleted_since_cursor": cursor_initial,
                        "filters_hash": "hash_anciens_filtres",
                        "force_full_sync": False,
                    }
                ]
            }
        )
        dn_server = FakeDemarchesServer(
            [
                make_dossier(1, dateDerniereModification="2024-07-01T00:00:00Z"),
                make_dossier(2, dateDerniereModification="2024-05-01T00:00:00Z"),
            ]
        )

        result, _ = run_pipeline(server, dn_server, parallel=False)

        assert result is True
        assert sorted(server.column(DOSSIERS_TABLE, "dossier_number")) == [1, 2]
        assert server.metadata(DEMARCHE_NUMBER)["last_sync_status"] == "success"

    def test_pipeline_updates_existing_dossier_without_duplicate(self):
        """Un dossier déjà présent dans le document est mis à jour, pas dupliqué."""
        server = FakeGristServer(
            initial_records={
                DOSSIERS_TABLE: [
                    {
                        "dossier_id": "dossier_1",
                        "dossier_number": 1,
                        "state": "en_instruction",
                    }
                ]
            }
        )
        dn_server = FakeDemarchesServer([make_dossier(1)])

        result, _ = run_pipeline(server, dn_server, parallel=False)

        assert result is True

        lignes = server.rows(DOSSIERS_TABLE)
        assert len(lignes) == 1
        assert lignes[0]["state"] == "accepte"
        assert lignes[0]["suivi_par"] == "inst@test.fr"

    def test_dn_pagination_writes_every_dossier(self):
        """201 dossiers servis par l'API DN en plusieurs pages : l'état final
        Grist doit contenir chaque dossier une seule fois, avec ses champs,
        annotations et avis.

        Régression : dossier perdu ou dupliqué à la frontière des pages, ou
        query paginée qui ne demanderait plus les détails des dossiers.
        """
        numbers = list(range(1, 202))
        dn_server = FakeDemarchesServer(dossiers_de_test(201))
        server = FakeGristServer()

        result, _ = run_pipeline(server, dn_server, parallel=False)

        assert result is True

        # L'égalité des listes (et non des sets) garantit l'absence de doublon
        assert sorted(server.column(DOSSIERS_TABLE, "dossier_number")) == numbers
        assert set(server.column(CHAMPS_TABLE, "dossier_number")) == set(numbers)
        assert set(server.column(ANNOTATIONS_TABLE, "dossier_number")) == set(numbers)
        assert set(server.column(AVIS_TABLE, "dossier_number")) == set(numbers)
        assert len(set(server.column(AVIS_TABLE, "avis_id"))) == len(numbers)
        assert server.metadata(DEMARCHE_NUMBER)["last_sync_status"] == "success"

    def test_dn_filters_keep_expected_dossiers_across_pages(self):
        """Le filtrage de la production ne doit faire perdre aucun dossier
        éligible, et les bornes de dates restent inclusives.

        Scénario : la première page est presque entièrement écartée, les pages
        suivantes contiennent les dossiers éligibles et trois cas limites (un
        statut non filtré, un groupe non filtré, une date trop tardive).

        Régression : dossier sauté parce qu'il se trouvait après une zone
        filtrée, ou borne de date devenue exclusive.
        """
        numbers = list(range(1, 202))
        debut, fin = "2024-03-01", "2024-06-19"
        hors_periode = "2024-01-05T09:00:00Z"  # avant DATE_DEPOT_DEBUT
        dans_periode = "2024-06-15T09:00:00Z"
        hors_fin = "2024-06-20T09:00:00Z"  # après DATE_DEPOT_FIN

        dossiers = [
            make_dossier(
                number,
                dateDepot=dans_periode,
                groupeInstructeur={"id": "groupe_1", "number": 1, "label": "G1"},
            )
            for number in numbers
        ]
        # Page 1 : tous hors période, sauf le dossier 50 exactement sur la borne
        for dossier in dossiers[:100]:
            dossier["dateDepot"] = hors_periode
        dossiers[49]["dateDepot"] = debut + "T00:00:00Z"
        # Un statut non filtré, un groupe non filtré, une date trop tardive
        dossiers[119]["state"] = "refuse"
        dossiers[129]["groupeInstructeur"] = {
            "id": "groupe_2",
            "number": 2,
            "label": "G2",
        }
        dossiers[150]["dateDepot"] = hors_fin
        # Le dossier 201 est déposé le jour même de la borne haute : conservé
        dossiers[200]["dateDepot"] = fin + "T23:30:00Z"

        # Sont attendus : le dossier 50 (borne basse inclusive) et 201 (borne
        # haute inclusive), tous les dossiers 101 à 200 sauf 120 (statut),
        # 130 (groupe) et 151 (borne haute).
        attendus = {50, 201} | (set(range(101, 201)) - {120, 130, 151})

        dn_server = FakeDemarchesServer(dossiers)
        server = FakeGristServer()

        result, _ = run_pipeline(
            server,
            dn_server,
            filters={
                "DATE_DEPOT_DEBUT": debut,
                "DATE_DEPOT_FIN": fin,
                "STATUTS_DOSSIERS": "accepte",
                "GROUPES_INSTRUCTEURS": "1",
            },
            parallel=False,
        )

        assert result is True
        assert set(server.column(DOSSIERS_TABLE, "dossier_number")) == attendus
        assert server.metadata(DEMARCHE_NUMBER)["last_sync_status"] == "success"

    def test_dn_page_error_keeps_resume_marker(self):
        """Une page perdue en cours de parcours ne doit pas faire avancer le
        repère de reprise, sinon ses dossiers ne seraient jamais réintégrés.

        Scénario : 201 dossiers, l'API DN échoue sur la page 2. Les dossiers de la
        page 1 doivent être dans le document, ceux des pages suivantes absents, et
        les deux repères de reprise (`updated_since`, `deleted_since`) inchangés,
        la synchro étant marquée partielle.

        Régression : un repère avancé malgré la page perdue, qui effacerait
        définitivement les dossiers non reçus de l'API.
        """
        with patch.dict(os.environ, FILTRES_VIDES):
            hash_sans_filtre = build_filters_cache_key()

        cursor_initial = "2023-01-01T00:00:00Z"
        server = FakeGristServer(
            initial_records={
                SYNC_METADATA_TABLE: [
                    {
                        "demarche_number": DEMARCHE_NUMBER,
                        "updated_since_cursor": cursor_initial,
                        "deleted_since_cursor": cursor_initial,
                        "filters_hash": hash_sans_filtre,
                        "force_full_sync": False,
                    }
                ]
            }
        )
        dn_server = FakeDemarchesServer(dossiers_de_test(201), page_en_erreur=2)

        result, _ = run_pipeline(server, dn_server, parallel=False)

        # Les pages lues sont écrites, la page perdue et les suivantes sont absentes
        assert result is True
        assert server.column(DOSSIERS_TABLE, "dossier_number") == list(range(1, 101))
        assert set(server.column(CHAMPS_TABLE, "dossier_number")) == set(range(1, 101))

        metadata = server.metadata(DEMARCHE_NUMBER)
        assert metadata["last_sync_status"] == "partial"
        assert metadata["updated_since_cursor"] == cursor_initial
        assert metadata["deleted_since_cursor"] == cursor_initial

    def test_dossier_error_does_not_lose_other_dossiers(self):
        """Un dossier impossible à préparer ne doit pas faire perdre les autres.

        Régression : le dossier en échec et toute sa page perdus, ou une synchro
        déclarée réussie alors qu'un dossier n'a pas été écrit.
        """
        server = FakeGristServer()
        dn_server = FakeDemarchesServer(dossiers_de_test(10))
        preparation_reelle = gpa.dossier_to_flat_data

        def preparation_qui_casse_le_dossier_5(dossier, *args, **kwargs):
            if dossier.get("number") == 5:
                raise RuntimeError("extraction impossible")
            return preparation_reelle(dossier, *args, **kwargs)

        with patch.object(
            gpa,
            "dossier_to_flat_data",
            side_effect=preparation_qui_casse_le_dossier_5,
        ):
            result, _ = run_pipeline(server, dn_server, parallel=False)

        assert result is True
        attendus = [1, 2, 3, 4, 6, 7, 8, 9, 10]
        assert sorted(server.column(DOSSIERS_TABLE, "dossier_number")) == attendus
        assert set(server.column(CHAMPS_TABLE, "dossier_number")) == set(attendus)
        assert server.metadata(DEMARCHE_NUMBER)["last_sync_status"] == "partial"
