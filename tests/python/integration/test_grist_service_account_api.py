"""Tests d'intégration du client Grist pour les comptes de service.

Le transport HTTP est intercepté au seam `GristClient._get_session` et servi
par `FakeGristApi`, un faux serveur persistant : les comptes de service créés
et les accès posés sur le document sont conservés, l'état final est donc
observable (même convention que `FakeGristServer` du pipeline de sync).
"""

import datetime as dt
import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

import pytest
import requests

from grist.client import GristClient
from grist.service_account import (
    ServiceAccountsNotEnabledError,
    resolve_grist_api_key,
)
from grist.utils import GristKeyAccessError

BASE_URL = "https://grist.test"
DOC_ID = "doc123"


def build_response(payload, status=200):
    """Fabrique une vraie `requests.Response` avec le payload JSON voulu."""
    resp = requests.Response()
    resp.status_code = status
    resp._content = json.dumps(payload).encode("utf-8")
    resp.headers["Content-Type"] = "application/json"
    return resp


class FakeGristApi:
    """Mini API Grist en mémoire : profil, comptes de service, accès document.

    `service_accounts` conserve les comptes créés (label, description,
    expiresAt, login, key) ; `doc_access` conserve, par document, les rôles
    posés via PATCH /docs/{doc}/access.
    """

    def __init__(
        self,
        email="user@example.com",
        service_accounts_enabled=True,
        doc_access_level="owners",
    ):
        self.email = email
        self.service_accounts_enabled = service_accounts_enabled
        self.doc_access_level = doc_access_level
        self.service_accounts = {}
        self.doc_access = {}
        self._next_sa_id = 0

    def handle(self, method, url, payload=None):
        method = method.upper()
        parts = [p for p in urlparse(url).path.split("/") if p]

        if method == "GET" and parts == ["profile", "user"]:
            return build_response({"id": 1, "email": self.email, "name": "User"})

        if method == "POST" and parts == ["service-accounts"]:
            if not self.service_accounts_enabled:
                return build_response({"error": "not found"}, status=404)
            self._next_sa_id += 1
            sa_id = self._next_sa_id
            login = f"sa-{sa_id}@serviceaccounts.invalid"
            key = f"key-sa-{sa_id}"
            self.service_accounts[sa_id] = {
                "label": payload.get("label"),
                "description": payload.get("description"),
                "expiresAt": payload.get("expiresAt"),
                "login": login,
                "key": key,
            }
            return build_response(
                {
                    "id": sa_id,
                    "login": login,
                    "key": key,
                    "label": payload.get("label"),
                    "description": payload.get("description"),
                    "expiresAt": payload.get("expiresAt"),
                    "hasValidKey": True,
                }
            )

        if method == "GET" and len(parts) == 2 and parts[0] == "docs":
            return build_response({"id": parts[1], "access": self.doc_access_level})

        if (
            method == "PATCH"
            and len(parts) == 3
            and parts[:2] == ["docs", parts[1]]
            and parts[2] == "access"
        ):
            doc_id = parts[1]
            users = (payload or {}).get("delta", {}).get("users", {})
            self.doc_access.setdefault(doc_id, {}).update(users)
            return build_response({"users": dict(self.doc_access[doc_id])})

        raise AssertionError(f"Requête non prévue : {method} {parts}")


@contextmanager
def grist_transport(server):
    """`GristClient` branché sur `server` via le seam `GristClient._get_session`."""
    client = GristClient(BASE_URL, "user-key", DOC_ID)
    session = MagicMock()
    for method in ("get", "post", "patch"):
        getattr(session, method).side_effect = lambda *args, method=method, **kwargs: (
            server.handle(method, args[0], kwargs.get("json"))
        )
    with patch.object(GristClient, "_get_session", return_value=session):
        yield client


class TestCreateServiceAccount:
    def test_created_account_is_persisted_with_label_and_expiry(self):
        """Le compte de service créé est conservé avec son label et expiresAt."""
        server = FakeGristApi()
        with grist_transport(server) as client:
            result = client.create_service_account(
                "OTP-DS-to-Grist — user@example.com",
                f"doc {DOC_ID}",
                "2027-11-01T00:00:00.000Z",
            )

        assert result["key"] == "key-sa-1"
        assert result["login"].endswith("@serviceaccounts.invalid")
        assert server.service_accounts[1] == {
            "label": "OTP-DS-to-Grist — user@example.com",
            "description": f"doc {DOC_ID}",
            "expiresAt": "2027-11-01T00:00:00.000Z",
            "login": result["login"],
            "key": "key-sa-1",
        }

    def test_disabled_service_accounts_returns_404(self):
        """Instance sans GRIST_ENABLE_SERVICE_ACCOUNTS -> 404, aucun compte créé."""
        server = FakeGristApi(service_accounts_enabled=False)
        with grist_transport(server) as client:
            with pytest.raises(requests.HTTPError):
                client.create_service_account(
                    "label", "desc", "2027-11-01T00:00:00.000Z"
                )

        assert server.service_accounts == {}


class TestUpdateDocAccess:
    def test_owner_role_is_persisted_on_document(self):
        """PATCH /docs/{doc}/access conserve le rôle owners posé."""
        server = FakeGristApi()
        with grist_transport(server) as client:
            client.update_doc_access({"sa-1@serviceaccounts.invalid": "owners"})

        assert server.doc_access[DOC_ID] == {"sa-1@serviceaccounts.invalid": "owners"}


class TestResolveGristApiKey:
    """`resolve_grist_api_key` de bout en bout contre le faux serveur Grist."""

    def test_user_key_creates_service_account_attached_as_owner(self):
        """Clé utilisateur -> compte de service créé, attaché en owners au doc."""
        server = FakeGristApi(email="user@example.com")
        with grist_transport(server):
            result = resolve_grist_api_key(BASE_URL, "user-key", DOC_ID)

        assert result.service_account_created
        assert result.api_key == "key-sa-1"
        assert result.owner_email == "user@example.com"

        created = server.service_accounts[1]
        assert created["label"] == "OTP-DS-to-Grist — user@example.com"
        assert DOC_ID in created["description"]
        today = dt.date.today()
        expires = dt.date.fromisoformat(created["expiresAt"][:10])
        assert (expires.day, expires.month, expires.year) == (
            1,
            today.month,
            today.year + 1,
        )
        assert server.doc_access[DOC_ID] == {created["login"]: "owners"}

    def test_service_account_key_used_as_is(self):
        """Clé de compte de service -> telle quelle, rien n'est créé ni modifié."""
        server = FakeGristApi(email="sa-9@serviceaccounts.invalid")
        with grist_transport(server):
            result = resolve_grist_api_key(BASE_URL, "sa-key", DOC_ID)

        assert result.api_key == "sa-key"
        assert not result.service_account_created
        assert result.owner_email == "sa-9@serviceaccounts.invalid"
        assert server.service_accounts == {}
        assert server.doc_access == {}

    def test_service_accounts_not_enabled_raises_clear_error(self):
        """Instance sans comptes de service -> erreur explicite, rien de créé."""
        server = FakeGristApi(email="user@example.com", service_accounts_enabled=False)
        with grist_transport(server):
            with pytest.raises(ServiceAccountsNotEnabledError):
                resolve_grist_api_key(BASE_URL, "user-key", DOC_ID)

        assert server.service_accounts == {}
        assert server.doc_access == {}

    def test_service_account_key_without_owner_access_fails(self):
        """Clé de compte de service sans droit propriétaire sur le doc -> erreur."""
        server = FakeGristApi(
            email="sa-9@serviceaccounts.invalid", doc_access_level="editors"
        )
        with grist_transport(server):
            with pytest.raises(GristKeyAccessError):
                resolve_grist_api_key(BASE_URL, "sa-key", DOC_ID)

        assert server.service_accounts == {}
        assert server.doc_access == {}
