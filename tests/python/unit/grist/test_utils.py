from unittest.mock import MagicMock

import pytest
import requests

from grist.base_url import GristBaseUrlNotAllowedError
from grist.utils import (
    GristKeyInsufficientAccessError,
    GristKeyNoAccessError,
    GristUnavailableError,
    normalize_column_name,
    require_owner_access,
)

BASE_URL = "https://grist.example.com/api"


class TestNormalizeColumnName:
    """Tests unitaires pour la fonction normalize_column_name"""

    def test_normalize_column_name_basic(self):
        """Test de normalisation basique"""
        assert normalize_column_name("Nom du champ") == "nom_du_champ"
        assert normalize_column_name("Prénom") == "prenom"
        assert normalize_column_name("Email@domain.com") == "email_domain_com"

    def test_normalize_column_name_empty(self):
        """Test avec chaîne vide"""
        assert normalize_column_name("") == "column"
        assert normalize_column_name("   ") == "column"
        assert normalize_column_name("!!!") == "column"
        assert normalize_column_name(None) == "column"

    def test_normalize_column_name_special_chars(self):
        """Test avec caractères spéciaux"""
        assert normalize_column_name("Champ#1!") == "champ_1"
        assert normalize_column_name("Test-Field_123") == "test_field_123"

    def test_normalize_column_name_accents(self):
        """Test avec accents"""
        assert normalize_column_name("Téléphone") == "telephone"
        assert normalize_column_name("Adresse naïve") == "adresse_naive"

    def test_normalize_column_name_multiple_spaces(self):
        """Test avec espaces multiples"""
        assert normalize_column_name("Champ   avec   espaces") == "champ_avec_espaces"

    def test_normalize_column_name_underscores(self):
        """Test avec underscores multiples"""
        assert (
            normalize_column_name("champ__avec__underscores")
            == "champ_avec_underscores"
        )

    def test_normalize_column_name_starts_with_number(self):
        """Test qui commence par un chiffre"""
        assert normalize_column_name("123champ") == "col_123champ"

    def test_normalize_column_name_max_length(self):
        """Test de longueur maximale"""
        long_name = "a" * 60
        result = normalize_column_name(long_name, max_length=50)
        assert len(result) <= 50
        # Function adds hash suffix when truncating: name[:43] + "_" + hash[:6]
        assert result.startswith("a" * 43 + "_")
        assert len(result) == 50

    def test_normalize_column_name_edge_cases(self):
        """Test de cas limites"""
        assert normalize_column_name("_underscore") == "underscore"
        assert normalize_column_name("underscore_") == "underscore"
        assert normalize_column_name("___multiple___") == "multiple"

    def test_normalize_column_name_none(self):
        """None -> nom par défaut"""
        assert normalize_column_name(None) == "column"

    def test_normalize_column_name_apostrophes(self):
        """Les apostrophes séparent les mots"""
        assert normalize_column_name("Nom de l'élève") == "nom_de_l_eleve"
        assert normalize_column_name("l’enseignant") == "l_enseignant"
        assert normalize_column_name("l`enseignant") == "l_enseignant"

    def test_normalize_column_name_strips_leading_numbering(self):
        """La numérotation en tête de libellé est retirée"""
        assert normalize_column_name("1. Nom de l'élève") == "nom_de_l_eleve"
        assert normalize_column_name("2) Date") == "date"
        assert normalize_column_name("3.Adresse") == "adresse"
        assert normalize_column_name("12. Bloc") == "bloc"

    def test_normalize_column_name_keeps_number_without_separator(self):
        """Un nombre sans point ni parenthèse fait partie du libellé"""
        assert normalize_column_name("12 mois") == "col_12_mois"
        assert normalize_column_name("Étape 1. Dépôt") == "etape_1_depot"

    def test_normalize_column_name_max_length_is_stable(self):
        """La troncature est déterministe et distingue deux libellés proches"""
        a = normalize_column_name("x" * 200 + "a")
        b = normalize_column_name("x" * 200 + "b")
        assert len(a) == 150
        assert a == normalize_column_name("x" * 200 + "a")
        assert a != b


def _http_error(status_code: int) -> requests.exceptions.HTTPError:
    response = requests.Response()
    response.status_code = status_code

    return requests.exceptions.HTTPError(response=response)


def _patch_grist_client(
    monkeypatch,
    *,
    document_info: object = None,
    error: Exception | None = None,
):
    """Remplace GristClient dans grist.utils par un faux client."""
    get_document_info = MagicMock()
    if error is not None:
        get_document_info.side_effect = error
    else:
        get_document_info.return_value = document_info
    client_instance = MagicMock()
    client_instance.get_document_info = get_document_info
    client_cls = MagicMock(return_value=client_instance)
    monkeypatch.setattr("grist.utils.GristClient", client_cls)

    return client_cls


class TestRequireOwnerAccess:
    """Seule une clé propriétaire du document est acceptée, tout le reste échoue."""

    def test_owner_key_returns_document_info(self, monkeypatch):
        document_info = {"name": "Doc", "access": "owners"}
        client_cls = _patch_grist_client(monkeypatch, document_info=document_info)

        assert require_owner_access(BASE_URL, "key", "docA") == document_info
        client_cls.assert_called_once_with(BASE_URL, "key", "docA")

    @pytest.mark.parametrize("access_level", ["editors", "viewers", "guests"])
    def test_other_level_is_insufficient(self, monkeypatch, access_level):
        _patch_grist_client(monkeypatch, document_info={"access": access_level})

        with pytest.raises(GristKeyInsufficientAccessError) as raised:
            require_owner_access(BASE_URL, "key", "docA")

        assert raised.value.access_level == access_level
        assert str(raised.value) == "Accès propriétaire requis sur le document Grist"

    def test_missing_access_is_insufficient(self, monkeypatch):
        """Réponse hors spécification de Grist (`access` obligatoire) : échec."""
        _patch_grist_client(monkeypatch, document_info={"name": "Doc"})

        with pytest.raises(GristKeyInsufficientAccessError):
            require_owner_access(BASE_URL, "key", "docA")

    @pytest.mark.parametrize("status_code", [401, 403, 404])
    def test_key_without_document_access(self, monkeypatch, status_code):
        _patch_grist_client(monkeypatch, error=_http_error(status_code))

        with pytest.raises(GristKeyNoAccessError) as raised:
            require_owner_access(BASE_URL, "key", "docA")

        assert str(raised.value) == "Clé API sans accès au document Grist"

    @pytest.mark.parametrize(
        "error",
        [
            _http_error(500),
            _http_error(502),
            _http_error(503),
            requests.exceptions.ConnectionError(),
            requests.exceptions.Timeout(),
            requests.exceptions.JSONDecodeError("illisible", "", 0),
            ValueError("Document ID is required"),
        ],
    )
    def test_unanswered_check_is_unavailable(self, monkeypatch, error):
        _patch_grist_client(monkeypatch, error=error)

        with pytest.raises(GristUnavailableError) as raised:
            require_owner_access(BASE_URL, "key", "docA")

        assert str(raised.value) == "Grist indisponible"

    def test_unreadable_document_info_is_unavailable(self, monkeypatch):
        """Réponse 200 qui n'est pas un document : illisible, donc échec."""
        _patch_grist_client(monkeypatch, document_info=["pas", "un", "document"])

        with pytest.raises(GristUnavailableError):
            require_owner_access(BASE_URL, "key", "docA")

    def test_base_url_outside_whitelist_is_not_masked(self, monkeypatch):
        """Le refus de la liste blanche garde son propre message."""
        monkeypatch.setattr(
            "grist.utils.GristClient",
            MagicMock(side_effect=GristBaseUrlNotAllowedError("hors liste")),
        )

        with pytest.raises(GristBaseUrlNotAllowedError):
            require_owner_access(BASE_URL, "key", "docA")
