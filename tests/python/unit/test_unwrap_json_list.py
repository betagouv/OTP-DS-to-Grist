from queries_extract import unwrap_json_list

def test_liste_json_simple():
    assert unwrap_json_list('["Axe 1 : Transitions climatiques"]') == "Axe 1 : Transitions climatiques"

def test_liste_json_multiple():
    assert unwrap_json_list('["Axe 1", "Axe 2"]') == "Axe 1, Axe 2"

def test_string_normale():
    assert unwrap_json_list("65 - Haute-Pyrénées") == "65 - Haute-Pyrénées"

def test_string_vide():
    assert unwrap_json_list("") == ""

def test_json_invalide():
    assert unwrap_json_list("[pas du json]") == "[pas du json]"
