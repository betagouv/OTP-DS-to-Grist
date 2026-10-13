# tests/python/integration/conftest.py
import base64
import json

import pytest
from flask.testing import FlaskClient

from app import app
from configuration.config_manager import ConfigManager

WIDGET_HEADER = "X-Grist-Widget-Token"

DEFAULT_IDENTITY = {"userId": "userA", "docId": "docA", "readOnly": False}

STORED_CONFIG = {
    "otp_config_id": 1,
    "ds_api_token": "stored-token",
    "demarche_number": "123",
    "grist_base_url": "https://grist.example.com/api",
    "grist_api_key": "stored-key",
    "grist_doc_id": "docA",
    "grist_user_id": "userA",
}


def make_token(identity):
    """Construit un jeton widget factice portant `identity` (signature non vérifiée)."""
    raw = json.dumps(identity).encode()
    payload = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"header.{payload}.signature"


class AuthenticatedClient(FlaskClient):
    """
    Client de test qui présente un jeton widget par défaut.

    L'identité portée par le jeton se pilote par les attributs `identity`,
    `raw_token`, `anonymous` et `validation_error`, modifiés dans le test avant
    la requête. Un en-tête jeton fourni explicitement l'emporte.
    """

    identity = DEFAULT_IDENTITY
    raw_token = None
    anonymous = False
    validation_error = None

    def open(self, *args, **kwargs):
        headers = dict(kwargs.get("headers") or {})
        if WIDGET_HEADER not in headers and not self.anonymous:
            headers[WIDGET_HEADER] = self.raw_token or make_token(self.identity)
        kwargs["headers"] = headers

        return super().open(*args, **kwargs)


@pytest.fixture
def client(monkeypatch):
    """Client authentifié : le seul mock externe est la validation du jeton par Grist."""
    app.config["TESTING"] = True
    monkeypatch.setattr(app, "test_client_class", AuthenticatedClient)
    test_client = app.test_client()

    def fake_validate(token, base_url, doc_id):
        if test_client.validation_error is not None:
            raise test_client.validation_error

        return dict(test_client.identity)

    monkeypatch.setattr("security.widget_auth.validate_widget_token", fake_validate)
    monkeypatch.setattr(
        "security.widget_auth._grist_key_owner_id",
        lambda base_url, api_key: test_client.identity["userId"],
    )

    with test_client:
        yield test_client


@pytest.fixture(autouse=True)
def stored_config(monkeypatch):
    """Une configuration est déjà stockée pour l'identité par défaut."""
    monkeypatch.setattr(
        ConfigManager,
        "load_config",
        lambda self, grist_user_id, grist_doc_id: [dict(STORED_CONFIG)],
    )


@pytest.fixture(autouse=True)
def stored_config_by_id(monkeypatch):
    """La configuration par identifiant est chargeable : aucun accès réel à la base.

    Sans ce stub, le chargement échoue (pas de base de test) et le contrôle
    d'appartenance refuse la requête avant d'atteindre la route testée.
    Un identifiant falsy (0) ne désigne aucune configuration : il suit la
    vraie implémentation.
    """
    real_load_config_by_id = ConfigManager.load_config_by_id

    def fake_load_config_by_id(
        self: ConfigManager, otp_config_id: int
    ) -> dict:
        if not otp_config_id:
            return real_load_config_by_id(self, otp_config_id)

        return dict(STORED_CONFIG)

    monkeypatch.setattr(ConfigManager, "load_config_by_id", fake_load_config_by_id)
