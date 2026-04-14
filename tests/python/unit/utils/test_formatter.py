from utils.formatter import unwrap_json_list


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
