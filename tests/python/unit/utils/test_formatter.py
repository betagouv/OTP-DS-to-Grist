from datetime import datetime, timezone

from utils.formatter import (
    build_filters_cache_key,
    format_json_value,
    to_local_iso,
    unwrap_json_list,
)


def test_liste_json_simple():
    assert (
        unwrap_json_list('["Axe 1 : Transitions climatiques"]')
        == "Axe 1 : Transitions climatiques"
    )


def test_liste_json_multiple():
    assert unwrap_json_list('["Axe 1", "Axe 2"]') == "Axe 1, Axe 2"


def test_string_normale():
    assert unwrap_json_list("65 - Haute-Pyrénées") == "65 - Haute-Pyrénées"


def test_string_vide():
    assert unwrap_json_list("") == ""


def test_json_invalide():
    assert unwrap_json_list("[pas du json]") == "[pas du json]"


def test_liste_vide():
    assert unwrap_json_list("[]") == ""


def test_liste_nombres():
    assert unwrap_json_list("[1, 2, 3]") == "1, 2, 3"


def test_liste_types_mixtes():
    assert unwrap_json_list('[1, "a"]') == "1, a"


def test_none_en_entree():
    assert unwrap_json_list(None) is None


def test_valeur_par_defaut_none():
    champ = {}
    raw = champ.get("stringValue") or champ.get("value")
    result = unwrap_json_list(raw)
    assert result is None


def test_to_local_iso_aware_utc():
    value = datetime(2026, 9, 3, 9, 50, tzinfo=timezone.utc)
    assert to_local_iso(value) == "2026-09-03T11:50:00"


def test_to_local_iso_naif_traite_comme_utc():
    value = datetime(2026, 9, 3, 9, 50)
    assert to_local_iso(value) == "2026-09-03T11:50:00"


def test_to_local_iso_none():
    assert to_local_iso(None) is None


def test_format_json_value_none():
    assert format_json_value(None) is None


def test_format_json_value_simple():
    assert format_json_value("abc") == '"abc"'


def test_format_json_value_dict():
    assert format_json_value({"a": 1}) == '{"a": 1}'


def test_format_json_value_tronque():
    result = format_json_value("abcdefghijklmnopqrstuvwxyz", max_length=10)
    assert result == '"abcdefghi' + "..."


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
