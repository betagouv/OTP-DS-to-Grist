import os
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

from sync.filters import (
    build_filters_cache_key,
    build_server_filters,
    filter_dossiers,
    read_filters_from_env,
)

FILTER_VARS = (
    "DATE_DEPOT_DEBUT",
    "DATE_DEPOT_FIN",
    "STATUTS_DOSSIERS",
    "GROUPES_INSTRUCTEURS",
)


@contextmanager
def env_filters(**values):
    """Environnement sans aucun filtre, puis avec les seules valeurs fournies."""
    with patch.dict(os.environ):
        for variable in FILTER_VARS:
            os.environ.pop(variable, None)
        os.environ.update(values)
        yield


class TestReadFiltersFromEnv:
    """Tests unitaires pour la fonction read_filters_from_env"""

    def test_no_env_returns_no_filter(self):
        with env_filters():
            assert read_filters_from_env() == {
                "date_debut": None,
                "date_fin": None,
                "statuts": [],
                "groupes": [],
            }

    def test_reads_all_filters(self):
        with env_filters(
            DATE_DEPOT_DEBUT="2024-01-15",
            DATE_DEPOT_FIN="2024-03-31",
            STATUTS_DOSSIERS="accepte,refuse",
            GROUPES_INSTRUCTEURS="7,12",
        ):
            filters = read_filters_from_env()

        assert filters["date_debut"] == datetime(2024, 1, 15)
        assert filters["date_fin"] == datetime(2024, 3, 31)
        assert filters["statuts"] == ["accepte", "refuse"]
        assert filters["groupes"] == ["7", "12"]

    def test_invalid_date_is_ignored(self):
        with env_filters(DATE_DEPOT_DEBUT="15/01/2024"):
            assert read_filters_from_env()["date_debut"] is None

    def test_empty_values_are_ignored(self):
        with env_filters(STATUTS_DOSSIERS="accepte,,  ,refuse"):
            assert read_filters_from_env()["statuts"] == ["accepte", "refuse"]


class TestFilterDossiers:
    """Tests unitaires pour la fonction filter_dossiers"""

    def test_no_filter_keeps_every_dossier(self):
        dossiers = [
            {"number": 1, "state": "accepte"},
            {"number": 2, "state": "refuse"},
            {"number": 3, "state": "accepte"},
        ]

        with env_filters():
            assert filter_dossiers(dossiers, read_filters_from_env()) == dossiers

    def test_filter_on_state(self):
        dossiers = [
            {"number": 1, "state": "accepte"},
            {"number": 2, "state": "refuse"},
            {"number": 3, "state": "accepte"},
        ]
        filters = {
            "date_debut": None,
            "date_fin": None,
            "statuts": ["accepte"],
            "groupes": [],
        }

        assert [d["number"] for d in filter_dossiers(dossiers, filters)] == [1, 3]

    def test_filter_on_groupe_instructeur(self):
        dossiers = [
            {"number": 1, "state": "accepte", "groupeInstructeur": {"number": 7}},
            {"number": 2, "state": "accepte", "groupeInstructeur": {"number": 12}},
            {"number": 3, "state": "accepte", "groupeInstructeur": None},
        ]
        filters = {
            "date_debut": None,
            "date_fin": None,
            "statuts": [],
            "groupes": ["12"],
        }

        assert [d["number"] for d in filter_dossiers(dossiers, filters)] == [2]

    def test_date_bounds_are_inclusive(self):
        dossiers = [
            {"number": 1, "dateDepot": "2024-01-01T09:00:00+01:00"},
            {"number": 2, "dateDepot": "2024-01-15T09:00:00+01:00"},
            {"number": 3, "dateDepot": "2024-02-01T09:00:00+01:00"},
        ]
        filters = {
            "date_debut": datetime(2024, 1, 1),
            "date_fin": datetime(2024, 1, 15),
            "statuts": [],
            "groupes": [],
        }

        assert [d["number"] for d in filter_dossiers(dossiers, filters)] == [1, 2]

    def test_dossier_without_readable_date_is_dropped_when_date_filter(self):
        dossiers = [
            {"number": 1, "dateDepot": None},
            {"number": 2},
            {"number": 3, "dateDepot": "pas une date"},
            {"number": 4, "dateDepot": "2024-01-15T09:00:00+01:00"},
        ]
        filters = {
            "date_debut": datetime(2024, 1, 1),
            "date_fin": None,
            "statuts": [],
            "groupes": [],
        }

        assert [d["number"] for d in filter_dossiers(dossiers, filters)] == [4]

    def test_filters_are_combined(self):
        dossiers = [
            {
                "number": 1,
                "state": "accepte",
                "groupeInstructeur": {"number": 7},
                "dateDepot": "2024-01-10T09:00:00+01:00",
            },
            {
                "number": 2,
                "state": "accepte",
                "groupeInstructeur": {"number": 7},
                "dateDepot": "2024-03-10T09:00:00+01:00",
            },
            {
                "number": 3,
                "state": "refuse",
                "groupeInstructeur": {"number": 7},
                "dateDepot": "2024-01-11T09:00:00+01:00",
            },
            {
                "number": 4,
                "state": "accepte",
                "groupeInstructeur": {"number": 12},
                "dateDepot": "2024-01-12T09:00:00+01:00",
            },
        ]
        filters = {
            "date_debut": datetime(2024, 1, 1),
            "date_fin": datetime(2024, 2, 1),
            "statuts": ["accepte"],
            "groupes": ["7"],
        }

        assert [d["number"] for d in filter_dossiers(dossiers, filters)] == [1]


class TestBuildFiltersCacheKey:
    """Tests unitaires pour build_filters_cache_key (détection de changement de filtres)"""

    def test_legacy_env_groupes_change_key(self, monkeypatch):
        """chemin legacy : un changement de GROUPES_INSTRUCTEURS doit changer la clé
        (sinon `filters_hash` est stable et la sync complète n'est jamais déclenchée)"""
        monkeypatch.delenv("GROUPES_INSTRUCTEURS", raising=False)
        monkeypatch.delenv("STATUTS_DOSSIERS", raising=False)
        monkeypatch.delenv("DATE_DEPOT_DEBUT", raising=False)
        monkeypatch.delenv("DATE_DEPOT_FIN", raising=False)
        key_vide = build_filters_cache_key()
        monkeypatch.setenv("GROUPES_INSTRUCTEURS", "5")
        key_avec_groupe = build_filters_cache_key()
        assert key_vide != key_avec_groupe

    def test_legacy_env_statuts_change_key(self, monkeypatch):
        monkeypatch.delenv("GROUPES_INSTRUCTEURS", raising=False)
        monkeypatch.delenv("STATUTS_DOSSIERS", raising=False)
        monkeypatch.delenv("DATE_DEPOT_DEBUT", raising=False)
        monkeypatch.delenv("DATE_DEPOT_FIN", raising=False)
        key_vide = build_filters_cache_key()
        monkeypatch.setenv("STATUTS_DOSSIERS", "en_construction")
        key_avec_statut = build_filters_cache_key()
        assert key_vide != key_avec_statut

    def test_legacy_env_dates_change_key(self, monkeypatch):
        monkeypatch.delenv("GROUPES_INSTRUCTEURS", raising=False)
        monkeypatch.delenv("STATUTS_DOSSIERS", raising=False)
        monkeypatch.delenv("DATE_DEPOT_DEBUT", raising=False)
        monkeypatch.delenv("DATE_DEPOT_FIN", raising=False)
        key_vide = build_filters_cache_key()
        monkeypatch.setenv("DATE_DEPOT_DEBUT", "2024-01-01")
        key_avec_date = build_filters_cache_key()
        assert key_vide != key_avec_date

    def test_legacy_env_list_order_normalized(self, monkeypatch):
        """ordre des valeurs legacy (groupes/statuts) normalisé -> même clé"""
        monkeypatch.delenv("STATUTS_DOSSIERS", raising=False)
        monkeypatch.delenv("DATE_DEPOT_DEBUT", raising=False)
        monkeypatch.delenv("DATE_DEPOT_FIN", raising=False)
        monkeypatch.setenv("GROUPES_INSTRUCTEURS", "5,3")
        a = build_filters_cache_key()
        monkeypatch.setenv("GROUPES_INSTRUCTEURS", "3,5")
        b = build_filters_cache_key()
        assert a == b


def _filters(date_debut=None, date_fin=None, statuts=None, groupes=None):
    return {
        "date_debut": date_debut,
        "date_fin": date_fin,
        "statuts": statuts or [],
        "groupes": groupes or [],
    }


class TestBuildServerFilters:
    """Tests unitaires pour la fonction build_server_filters"""

    def test_no_filter_sends_nothing(self):
        assert build_server_filters(_filters(), None) == {
            "groupe_numbers": [],
            "states": [],
            "created_since": None,
        }

    def test_groupes_and_statuts_are_sent(self):
        server_filters = build_server_filters(
            _filters(statuts=["en_instruction", "accepte"], groupes=["120382", "7"]),
            None,
        )

        assert server_filters["groupe_numbers"] == [120382, 7]
        assert server_filters["states"] == ["en_instruction", "accepte"]

    def test_full_sync_sends_date_debut_with_one_day_margin(self):
        """Marge d'un jour : DN compare un instant UTC, le filtre client un jour local"""
        server_filters = build_server_filters(
            _filters(date_debut=datetime(2026, 1, 1)), None
        )

        assert server_filters["created_since"] == "2025-12-31T00:00:00Z"

    def test_incremental_sync_does_not_send_date_debut(self):
        """DN ignorerait createdSince à côté d'updatedSince : rien n'est envoyé"""
        server_filters = build_server_filters(
            _filters(date_debut=datetime(2026, 1, 1)), "2026-10-01T00:00:00Z"
        )

        assert server_filters["created_since"] is None

    def test_date_fin_is_never_sent(self):
        """Aucun argument DN pour la date de fin : elle reste côté client"""
        server_filters = build_server_filters(
            _filters(date_fin=datetime(2026, 6, 30)), None
        )

        assert server_filters["created_since"] is None
        assert set(server_filters) == {"groupe_numbers", "states", "created_since"}

    @patch("sync.filters.log_error")
    def test_non_numeric_groupe_is_ignored(self, mock_log_error):
        server_filters = build_server_filters(
            _filters(groupes=["12", "groupe-a"]), None
        )

        assert server_filters["groupe_numbers"] == [12]
        assert "groupe-a" in mock_log_error.call_args.args[0]

    @patch("sync.filters.log_error")
    def test_unknown_statut_is_ignored(self, mock_log_error):
        server_filters = build_server_filters(
            _filters(statuts=["accepte", "instruit"]), None
        )

        assert server_filters["states"] == ["accepte"]
        assert "instruit" in mock_log_error.call_args.args[0]
