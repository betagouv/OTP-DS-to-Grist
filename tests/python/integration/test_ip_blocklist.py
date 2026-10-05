import time
from datetime import datetime, timezone

import pytest
from flask import jsonify

import app as app_module
from app import app
from security.ip_blocklist import ban_duration, parse_whitelist
from utils.constants import IP_BLOCKLIST_THRESHOLD, IP_BLOCKLIST_WINDOW_SECONDS


@app.route("/__blocklist-test__/absent")
def blocklist_test_absent():
    """404 rendu par une vue : la route existe, la ressource est absente."""
    return jsonify({"error": "not found"}), 404


@app.route("/__blocklist-test__/refus")
def blocklist_test_refus():
    """403 rendu par une vue : la vue refuse la requête."""
    return jsonify({"error": "Forbidden"}), 403


@app.route("/__blocklist-test__/requete-invalide")
def blocklist_test_requete_invalide():
    """400 rendu par une vue : paramètres manquants."""
    return jsonify({"error": "Bad Request"}), 400


@app.route("/__blocklist-test__/panne")
def blocklist_test_panne():
    """500 rendu par une vue : erreur côté serveur."""
    return jsonify({"error": "Internal Server Error"}), 500


@app.route("/__blocklist-test__/slash/")
def blocklist_test_slash():
    """Route à slash final : `/__blocklist-test__/slash` déclenche une 308."""
    return jsonify({"ok": True})


class FakeStore:
    """
    Store de bannissements sans base de données, avec expiration.

    Comme le store réel, il retient la fin de chaque bannissement et la durée
    est calculée par `ban_duration`, pas recopiée : le test exerce donc la
    vraie règle de croissance.
    """

    def __init__(self):
        self.banned_until = {}
        self.applied = []

    def is_banned(self, ip):
        return self.banned_until.get(ip, 0.0) > time.time()

    def apply_ban(self, ip):
        moment = time.time()
        self.applied.append(ip)
        ban_count = self.applied.count(ip)
        banned_until = moment + ban_duration(ban_count).total_seconds()
        self.banned_until[ip] = banned_until
        return datetime.fromtimestamp(banned_until, timezone.utc).replace(tzinfo=None)


def expire(store, ip):
    """Simule l'écoulement de la durée du bannissement de `ip`."""
    store.banned_until[ip] = time.time() - 1.0


def set_ban(store, ip):
    """Met `ip` en état de bannie, pour la durée d'un premier bannissement."""
    store.banned_until[ip] = time.time() + ban_duration(1).total_seconds()


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


class _Clock:
    """
    Horloge gelée pour app.py.

    Seule `time.time()` y est définie, qui est la seule horloge lue par app.py :
    la remplacer dans l'espace de noms du module suffit donc, et le reste du
    processus, horloge comprise, continue d'avancer.
    """

    def __init__(self, moment):
        self.moment = moment

    def time(self):
        return self.moment

    def advance(self, seconds):
        """Fait écouler `seconds` secondes."""
        self.moment += seconds


@pytest.fixture
def clock(monkeypatch):
    """Fige l'horloge d'app.py, pour faire écouler la fenêtre des compteurs."""
    gelee = _Clock(time.time())
    monkeypatch.setattr(app_module, "time", gelee)

    return gelee


_IP = "203.0.113.9"
_HEADERS = {"X-Real-IP": _IP}


def get(client, path, ip=_IP):
    return client.get(path, headers={"X-Real-IP": ip})


class TestBannissement:
    def test_requete_normale_pas_bloquee(self, store, client):
        assert get(client, "/").status_code == 200

    def test_ip_bannie_recue_403(self, store, client):
        set_ban(store, "203.0.113.9")
        assert get(client, "/").status_code == 403

    def test_403_intervient_avant_la_route(self, store, client):
        set_ban(store, "203.0.113.9")
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

    def test_une_ip_en_liste_blanche_passe_meme_bannie(
        self, store, client, monkeypatch
    ):
        """La liste blanche sert aussi à se débloquer d'un bannissement."""
        monkeypatch.setattr(
            app_module,
            "ip_blocklist_whitelist",
            parse_whitelist(["203.0.113.0/24"]),
        )
        set_ban(store, _IP)

        assert get(client, "/").status_code == 200

    def test_une_ip_bannie_ne_bloque_pas_les_autres(self, store, client):
        set_ban(store, "203.0.113.9")
        assert get(client, "/", ip="203.0.113.10").status_code == 200


class TestRequetesEnEchec:
    """Toutes les réponses 4xx comptent, où qu'elles soient produites."""

    def test_404_de_routage_compte(self, store, client):
        get(client, "/.env")
        assert "203.0.113.9" in app_module.ip_blocklist_hits

    def test_405_de_routage_compte(self, store, client):
        """Un scanner teste aussi les méthodes autorisées."""
        for _ in range(IP_BLOCKLIST_THRESHOLD):
            assert client.put("/api/sync-report", headers=_HEADERS).status_code == 405
        assert store.applied == ["203.0.113.9"]

    def test_redirection_ne_compte_pas(self, store, client):
        """Une 308 est une redirection, pas un échec."""
        for _ in range(IP_BLOCKLIST_THRESHOLD + 2):
            assert (
                client.get("/__blocklist-test__/slash", headers=_HEADERS).status_code
                == 308
            )
        assert app_module.ip_blocklist_hits == {}
        assert store.applied == []

    def test_404_de_vue_compte(self, store, client):
        """Une 404 rendue par une vue compte aussi."""
        for _ in range(IP_BLOCKLIST_THRESHOLD):
            assert get(client, "/__blocklist-test__/absent").status_code == 404
        assert store.applied == ["203.0.113.9"]

    def test_403_de_vue_compte(self, store, client):
        """Une 403 rendue par une vue compte aussi."""
        for _ in range(IP_BLOCKLIST_THRESHOLD):
            assert get(client, "/__blocklist-test__/refus").status_code == 403
        assert store.applied == ["203.0.113.9"]

    def test_400_de_vue_compte(self, store, client):
        for _ in range(IP_BLOCKLIST_THRESHOLD):
            get(client, "/__blocklist-test__/requete-invalide")
        assert store.applied == ["203.0.113.9"]

    def test_500_ne_compte_pas(self, store, client):
        """Une erreur du serveur n'est pas la faute du client qui la reçoit."""
        for _ in range(IP_BLOCKLIST_THRESHOLD + 2):
            assert get(client, "/__blocklist-test__/panne").status_code == 500
        assert app_module.ip_blocklist_hits == {}
        assert store.applied == []

    def test_404_static_ne_compte_pas(self, store, client):
        """`should_ignore_path` exclut maintenant `/static/`, et lui seul."""
        for _ in range(IP_BLOCKLIST_THRESHOLD + 2):
            assert get(client, "/static/nexiste-pas.js").status_code == 404
        assert app_module.ip_blocklist_hits == {}
        assert store.applied == []

    def test_200_ne_compte_pas(self, store, client):
        get(client, "/")
        assert app_module.ip_blocklist_hits == {}

    def test_sous_le_seuil_aucun_ban(self, store, client):
        for _ in range(IP_BLOCKLIST_THRESHOLD - 1):
            assert get(client, "/.env").status_code == 404
        assert store.applied == []

    def test_au_seuil_ban(self, store, client):
        for _ in range(IP_BLOCKLIST_THRESHOLD):
            get(client, "/.env")
        assert store.applied == ["203.0.113.9"]

    def test_compte_par_ip(self, store, client):
        get(client, "/.env", ip="203.0.113.9")
        get(client, "/.env", ip="203.0.113.10")
        assert sorted(app_module.ip_blocklist_hits) == ["203.0.113.10", "203.0.113.9"]


class TestBannieQuiInsiste:
    """Une IP bannie n'est pas recomptée, et son bannissement ne s'allonge pas."""

    def test_403_bannie_ne_compte_pas(self, store, client):
        set_ban(store, _IP)

        for _ in range(IP_BLOCKLIST_THRESHOLD + 2):
            assert get(client, "/.env").status_code == 403

        assert app_module.ip_blocklist_hits == {}
        assert store.applied == []

    def test_ban_n_est_pas_allonge_par_les_requetes(self, store, client):
        for _ in range(IP_BLOCKLIST_THRESHOLD):
            get(client, "/.env")
        assert store.applied == [_IP]

        banned_until = store.banned_until[_IP]

        for _ in range(IP_BLOCKLIST_THRESHOLD + 2):
            assert get(client, "/.env").status_code == 403

        assert store.applied == [_IP]
        assert store.banned_until[_IP] == banned_until

    def test_escalade_seulement_apres_expiration(self, store, client):
        """Le bannissement s'allonge au retour de l'IP, une fois la durée écoulée."""
        for _ in range(IP_BLOCKLIST_THRESHOLD):
            get(client, "/.env")
        assert store.applied == [_IP]
        premiere_fin = store.banned_until[_IP]
        assert premiere_fin == pytest.approx(
            time.time() + ban_duration(1).total_seconds(), abs=10
        )

        for _ in range(IP_BLOCKLIST_THRESHOLD + 2):
            assert get(client, "/.env").status_code == 403

        assert store.banned_until[_IP] == premiere_fin

        expire(store, _IP)

        for _ in range(IP_BLOCKLIST_THRESHOLD):
            get(client, "/.env")

        assert store.applied == [_IP, _IP]
        assert store.banned_until[_IP] == pytest.approx(
            time.time() + ban_duration(2).total_seconds(), abs=10
        )


class TestMenageDesCompteurs:
    """Les IP dont plus aucune erreur n'est récente finissent par être oubliées."""

    def test_les_ips_expirees_sont_oubliees(self, store, client, clock):
        for index in range(3):
            get(client, "/.env", ip=f"203.0.113.{index}")
        assert len(app_module.ip_blocklist_hits) == 3

        clock.advance(IP_BLOCKLIST_WINDOW_SECONDS + 1)
        get(client, "/.env", ip="203.0.113.200")

        assert list(app_module.ip_blocklist_hits) == ["203.0.113.200"]

    def test_les_ips_sont_conservees_avant_la_frontiere(self, store, client, clock):
        for index in range(3):
            get(client, "/.env", ip=f"203.0.113.{index}")

        clock.advance(IP_BLOCKLIST_WINDOW_SECONDS / 2)
        get(client, "/.env", ip="203.0.113.200")

        assert len(app_module.ip_blocklist_hits) == 4

    def test_une_ip_qui_pause_repart_de_zero(self, store, client, clock):
        """Oublier une IP expirée ne peut pas non plus déclencher un ban."""
        for _ in range(IP_BLOCKLIST_THRESHOLD - 1):
            get(client, "/.env")

        clock.advance(IP_BLOCKLIST_WINDOW_SECONDS + 1)
        get(client, "/.env")

        assert store.applied == []
