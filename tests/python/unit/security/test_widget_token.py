import base64
import json
from unittest.mock import MagicMock, patch

import pytest
import requests

import grist.base_url
from grist.base_url import GristBaseUrlNotAllowedError
from security.widget_token import (
    WidgetTokenInvalidError,
    WidgetTokenUnavailableError,
    clear_validation_cache,
    decode_widget_token_identity,
    extract_widget_token,
    validate_widget_token,
)


def make_token(payload):
    def encode(obj):
        raw = json.dumps(obj).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"header.{encode(payload)}.signature"


@pytest.fixture(autouse=True)
def _isolate_cache():
    clear_validation_cache()
    yield
    clear_validation_cache()


class TestExtractWidgetToken:
    def test_returns_header_value(self):
        """L'en-tête porteur du jeton est lu."""
        assert extract_widget_token({"X-Grist-Widget-Token": "abc"}) == "abc"

    def test_missing_returns_none(self):
        assert extract_widget_token({}) is None

    def test_blank_returns_none(self):
        assert extract_widget_token({"X-Grist-Widget-Token": "   "}) is None

    def test_strips_whitespace(self):
        assert extract_widget_token({"X-Grist-Widget-Token": "  abc  "}) == "abc"


class TestDecodeWidgetTokenIdentity:
    def test_reads_payload(self):
        """Le contenu non signé est décodé tel quel."""
        token = make_token({"userId": 5, "docId": "doc", "readOnly": False})

        assert decode_widget_token_identity(token) == {
            "userId": 5,
            "docId": "doc",
            "readOnly": False,
        }

    def test_malformed_raises(self):
        with pytest.raises(WidgetTokenInvalidError):
            decode_widget_token_identity("not-a-token")


class TestValidateWidgetToken:
    def _response(self, status_code):
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = {}
        return response

    def _allowed(self, monkeypatch):
        monkeypatch.setattr(
            grist.base_url, "BASE_URL_WHITELIST", ("grist.example.com",)
        )

    def test_success_returns_identity(self, monkeypatch):
        """200 -> contenu du jeton ; appel présenté sur les tables du document."""
        self._allowed(monkeypatch)
        token = make_token(
            {"userId": 5, "docId": "doc", "readOnly": False, "exp": 9999999999}
        )

        with patch(
            "security.widget_token.requests.get", return_value=self._response(200)
        ) as get:
            identity = validate_widget_token(token, "https://grist.example.com/api", "doc")

        assert identity["userId"] == 5
        assert get.call_args.args[0] == "https://grist.example.com/api/docs/doc/tables"
        assert get.call_args.kwargs["params"] == {"auth": token}

    def test_success_is_cached(self, monkeypatch):
        """Deux vérifications du même jeton ne font qu'un appel à Grist."""
        self._allowed(monkeypatch)
        token = make_token({"userId": 5, "docId": "doc", "exp": 9999999999})

        with patch(
            "security.widget_token.requests.get", return_value=self._response(200)
        ) as get:
            validate_widget_token(token, "https://grist.example.com/api", "doc")
            validate_widget_token(token, "https://grist.example.com/api", "doc")

        assert get.call_count == 1

    @pytest.mark.parametrize("status_code", [401, 403])
    def test_rejected_token_raises_invalid(self, monkeypatch, status_code):
        """Jeton refusé par Grist -> jeton invalide."""
        self._allowed(monkeypatch)
        token = make_token({"userId": 5, "docId": "doc"})

        with patch(
            "security.widget_token.requests.get",
            return_value=self._response(status_code),
        ):
            with pytest.raises(WidgetTokenInvalidError):
                validate_widget_token(token, "https://grist.example.com/api", "doc")

    def test_server_error_raises_unavailable(self, monkeypatch):
        """5xx de Grist -> vérification impossible."""
        self._allowed(monkeypatch)
        token = make_token({"userId": 5, "docId": "doc"})

        with patch(
            "security.widget_token.requests.get", return_value=self._response(500)
        ):
            with pytest.raises(WidgetTokenUnavailableError):
                validate_widget_token(token, "https://grist.example.com/api", "doc")

    def test_network_error_raises_unavailable(self, monkeypatch):
        """Réseau coupé -> vérification impossible."""
        self._allowed(monkeypatch)
        token = make_token({"userId": 5, "docId": "doc"})

        with patch(
            "security.widget_token.requests.get",
            side_effect=requests.RequestException("boom"),
        ):
            with pytest.raises(WidgetTokenUnavailableError):
                validate_widget_token(token, "https://grist.example.com/api", "doc")

    def test_disallowed_base_url_raises(self, monkeypatch):
        """Instance hors liste blanche -> refus, sans appel réseau."""
        monkeypatch.setattr(
            grist.base_url, "BASE_URL_WHITELIST", ("grist.example.com",)
        )
        token = make_token({"userId": 5, "docId": "doc"})

        with patch("security.widget_token.requests.get") as get:
            with pytest.raises(GristBaseUrlNotAllowedError):
                validate_widget_token(token, "https://evil.example/api", "doc")

        get.assert_not_called()
