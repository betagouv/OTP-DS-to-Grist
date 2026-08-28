from utils.formatter import unwrap_json_list, build_filters_key


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


class TestBuildFiltersKey:
    """Tests unitaires pour build_filters_key (détection de changement de filtres)"""

    def test_same_filters_same_key(self):
        """mêmes filtres -> même clé (déterminisme)"""
        filters = {"statuts": ["en_construction"], "date_debut": "2024-01-01"}
        assert build_filters_key(filters) == build_filters_key(filters)

    def test_different_filters_different_key(self):
        """filtres différents -> clé différente"""
        assert build_filters_key({"statuts": ["en_construction"]}) != build_filters_key(
            {"statuts": ["en_instruction"]}
        )

    def test_no_filter_returns_non_none_key(self):
        """aucun filtre (None ou vide) -> clé déterministe non-None, jamais ambiguë"""
        key = build_filters_key(None)
        assert key is not None
        assert key == build_filters_key({})
        assert '"date_debut": null' in key
        assert key != build_filters_key({"statuts": ["en_construction"]})

    def test_list_order_is_normalized(self):
        """ordre différent des statuts/groupes -> même clé (tri)"""
        a = build_filters_key({"statuts": ["b", "a", "c"]})
        b = build_filters_key({"statuts": ["c", "a", "b"]})
        assert a == b

    def test_key_is_readable_json(self):
        """clé lisible JSON avec les 4 champs de filtres"""
        key = build_filters_key({"statuts": ["en_construction"], "groupes_instructeurs": ["5"]})
        assert "statuts" in key and "groupes_instructeurs" in key
        assert "en_construction" in key and "5" in key
