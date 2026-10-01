import pytest
from flask import jsonify, request

import app as app_module
from app import app
from security.ip_blocklist import parse_whitelist
from utils.constants import IP_BLOCKLIST_THRESHOLD


@app.route("/__blocklist-test__/absent")
def blocklist_test_absent():
    """404 applicatif : la route existe, la ressource est absente."""
    return jsonify({"error": "not found"}), 404


class FakeStore:
    """Store de bannissements sans base de données."""

    def __init__(self):
        self.banned = set()
        self.applied = []

    def is_banned(self, ip, now=None):
        return ip in self.banned

    def apply_ban(self, ip, now=None):
        self.applied.append(ip)
        self.banned.add(ip)
        return None


@pytest.fixture
def store(monkeypatch):
    """Remplace le store réel et remet à zéro l'état de la blocklist."""
    fake = FakeStore()
    monkeypatch.setattr(app_module, "ip_blocklist_store", fake)
    monkeypatch.setattr(app_module, "ip_blocklist_whitelist", ())
    monkeypatch.setattr(app_module, "ip_blocklist_hits", {})

    return fake


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def get(client, path, ip="203.0.113.9"):
    return client.get(path, headers={"X-Real-IP": ip})


class TestBannissement:
    def test_requete_normale_pas_bloquee(self, store, client):
        assert get(client, "/").status_code == 200

    def test_ip_bannie_recue_403(self, store, client):
        store.banned.add("203.0.113.9")
        assert get(client, "/").status_code == 403

    def test_403_intervient_avant_la_route(self, store, client):
        store.banned.add("203.0.113.9")
        assert get(client, "/__blocklist-test__/absent").status_code == 403

    def test_sans_entete_ip_aucun_blocage(self, store, client):
        response = client.get("/__blocklist-test__/absent")
        assert response.status_code == 404
        assert store.applied == []

    def test_entete_malforme_ne_bannit_pas(self, store, client):
        for _ in range(IP_BLOCKLIST_THRESHOLD + 2):
            client.get("/.env", headers={"X-Real-IP": "pas-une-ip"})
        assert store.applied == []

    def test_whitelist_jamais_bannie(self, store, client, monkeypatch):
        monkeypatch.setattr(
            app_module,
            "ip_blocklist_whitelist",
            parse_whitelist(["203.0.113.0/24"]),
        )
        for _ in range(IP_BLOCKLIST_THRESHOLD + 2):
            get(client, "/.env", ip="203.0.113.9")
        assert store.applied == []
        assert get(client, "/").status_code == 200

    def test_une_ip_bannie_ne_bloque_pas_les_autres(self, store, client):
        store.banned.add("203.0.113.9")
        assert get(client, "/", ip="203.0.113.10").status_code == 200


class TestComptageDes404:
    def test_404_de_routage_compte(self, store, client):
        get(client, "/.env")
        assert "203.0.113.9" in app_module.ip_blocklist_hits

    def test_sous_le_seuil_aucun_ban(self, store, client):
        for _ in range(IP_BLOCKLIST_THRESHOLD - 1):
            assert get(client, "/.env").status_code == 404
        assert store.applied == []

    def test_au_seuil_ban(self, store, client):
        for _ in range(IP_BLOCKLIST_THRESHOLD):
            get(client, "/.env")
        assert store.applied == ["203.0.113.9"]

    def test_404_applicatif_ne_compte_pas(self, store, client):
        for _ in range(IP_BLOCKLIST_THRESHOLD + 2):
            assert get(client, "/__blocklist-test__/absent").status_code == 404
        assert app_module.ip_blocklist_hits == {}
        assert store.applied == []

    def test_404_static_ne_compte_pas(self, store, client):
        for _ in range(IP_BLOCKLIST_THRESHOLD + 2):
            assert get(client, "/static/nexiste-pas.js").status_code == 404
        assert app_module.ip_blocklist_hits == {}
        assert store.applied == []

    def test_200_ne_compte_pas(self, store, client):
        get(client, "/")
        assert app_module.ip_blocklist_hits == {}

    def test_compte_par_ip(self, store, client):
        get(client, "/.env", ip="203.0.113.9")
        get(client, "/.env", ip="203.0.113.10")
        assert sorted(app_module.ip_blocklist_hits) == ["203.0.113.10", "203.0.113.9"]

    def test_ban_puis_compte_reinitialise(self, store, client):
        for _ in range(IP_BLOCKLIST_THRESHOLD):
            get(client, "/.env")
        assert store.applied == ["203.0.113.9"]
        store.applied.clear()
        for _ in range(IP_BLOCKLIST_THRESHOLD - 1):
            get(client, "/.env")
        assert store.applied == []


class TestDiscriminantDeRoutage:
    """Contrat sur lequel repose l'exclusion des 404 applicatifs."""

    def test_url_rule_renseigne_pour_une_route_existante(self):
        with app.test_request_context("/api/sync-report"):
            assert request.url_rule is not None

    def test_url_rule_renseigne_pour_un_asset_manquant(self):
        with app.test_request_context("/static/nexiste-pas.js"):
            assert request.url_rule is not None

    def test_url_rule_none_pour_un_chemin_inconnu(self):
        with app.test_request_context("/.env"):
            assert request.url_rule is None