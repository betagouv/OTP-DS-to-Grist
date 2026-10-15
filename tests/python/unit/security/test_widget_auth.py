"""Tests unitaires du contrôle d'accès de la clé API Grist au document."""

from unittest.mock import MagicMock

import pytest
import requests

from security.widget_auth import (
    GRIST_KEY_ACCESS_UNSPECIFIED,
    GRIST_KEY_NO_ACCESS,
    grist_doc_access_level,
    is_key_write_allowed,
)

BASE_URL = "https://grist.example.com/api"


def _http_error(status_code: int) -> requests.exceptions.HTTPError:
    response = requests.Response()
    response.status_code = status_code

    return requests.exceptions.HTTPError(response=response)


def _patch_grist_client(
    monkeypatch,
    *,
    document_info: dict | None = None,
    error: Exception | None = None,
):
    """Remplace GristClient dans widget_auth par un faux client."""
    get_document_info = MagicMock()
    if error is not None:
        get_document_info.side_effect = error
    else:
        get_document_info.return_value = document_info
    client_instance = MagicMock()
    client_instance.get_document_info = get_document_info
    client_cls = MagicMock(return_value=client_instance)
    monkeypatch.setattr("security.widget_auth.GristClient", client_cls)

    return client_cls


class TestGristDocAccessLevel:
    """Niveau d'accès de la clé API sur le document ciblé."""

    def test_owners_access_returns_owners(self, monkeypatch):
        client_cls = _patch_grist_client(
            monkeypatch, document_info={"name": "Doc", "access": "owners"}
        )

        assert grist_doc_access_level(BASE_URL, "sa-key", "docA") == "owners"
        client_cls.assert_called_once_with(BASE_URL, "sa-key", "docA")

    def test_editors_access_returns_editors(self, monkeypatch):
        _patch_grist_client(monkeypatch, document_info={"access": "editors"})

        assert grist_doc_access_level(BASE_URL, "key", "docA") == "editors"

    def test_viewers_access_returns_viewers(self, monkeypatch):
        _patch_grist_client(monkeypatch, document_info={"access": "viewers"})

        assert grist_doc_access_level(BASE_URL, "key", "docA") == "viewers"

    def test_missing_access_returns_unspecified(self, monkeypatch):
        """200 sans champ `access` : niveau indéterminé, la clé est acceptée."""
        _patch_grist_client(monkeypatch, document_info={"name": "Doc"})

        assert (
            grist_doc_access_level(BASE_URL, "key", "docA")
            == GRIST_KEY_ACCESS_UNSPECIFIED
        )

    @pytest.mark.parametrize("status_code", [401, 403, 404])
    def test_key_without_document_access_returns_no_access(
        self, monkeypatch, status_code
    ):
        """La clé qui ne voit pas le document n'y a aucun accès."""
        _patch_grist_client(monkeypatch, error=_http_error(status_code))

        assert (
            grist_doc_access_level(BASE_URL, "key", "docA") == GRIST_KEY_NO_ACCESS
        )

    @pytest.mark.parametrize("status_code", [500, 502, 503])
    def test_server_error_returns_none(self, monkeypatch, status_code):
        _patch_grist_client(monkeypatch, error=_http_error(status_code))

        assert grist_doc_access_level(BASE_URL, "key", "docA") is None

    def test_network_error_returns_none(self, monkeypatch):
        _patch_grist_client(monkeypatch, error=requests.exceptions.ConnectionError())

        assert grist_doc_access_level(BASE_URL, "key", "docA") is None

    def test_timeout_returns_none(self, monkeypatch):
        _patch_grist_client(monkeypatch, error=requests.exceptions.Timeout())

        assert grist_doc_access_level(BASE_URL, "key", "docA") is None

    def test_unexpected_error_returns_none(self, monkeypatch):
        _patch_grist_client(monkeypatch, error=ValueError("Document ID is required"))

        assert grist_doc_access_level(BASE_URL, "key", "docA") is None


class TestIsKeyWriteAllowed:
    """Le prédicat partagé autorise owners/editors et le niveau indéterminé."""

    @pytest.mark.parametrize("access_level", ["owners", "editors"])
    def test_write_levels_are_allowed(self, access_level):
        assert is_key_write_allowed(access_level) is True

    def test_unspecified_level_is_allowed(self):
        assert is_key_write_allowed(GRIST_KEY_ACCESS_UNSPECIFIED) is True

    @pytest.mark.parametrize("access_level", ["viewers", GRIST_KEY_NO_ACCESS])
    def test_read_only_levels_are_refused(self, access_level):
        assert is_key_write_allowed(access_level) is False
