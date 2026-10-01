from datetime import timedelta

import pytest

from security.ip_blocklist import (
    BAN_BASE_SECONDS,
    BAN_MAX_SECONDS,
    ban_duration,
    is_whitelisted,
    parse_whitelist,
    register_hit,
    resolve_client_ip,
    should_ignore_path,
)


class TestResolveClientIp:
    def test_x_real_ip_prioritaire_sur_xff(self):
        headers = {
            "X-Real-IP": "203.0.113.7",
            "X-Forwarded-For": "203.0.113.99, 88.183.70.217",
        }
        assert resolve_client_ip(headers) == "203.0.113.7"

    def test_xff_a_plusieurs_valeurs_renvoie_la_droite(self):
        headers = {"X-Forwarded-For": "203.0.113.99, 10.0.0.22, 88.183.70.217"}
        assert resolve_client_ip(headers) == "88.183.70.217"

    def test_xff_forge_seul_renvoie_la_droite_ajoutee_par_scalingo(self):
        headers = {"X-Forwarded-For": "203.0.113.99, 88.183.70.217"}
        assert resolve_client_ip(headers) == "88.183.70.217"

    def test_entetes_insensibles_a_la_casse(self):
        headers = {"x-real-ip": "203.0.113.7", "x-forwarded-for": "10.0.0.22"}
        assert resolve_client_ip(headers) == "203.0.113.7"

    def test_x_real_ip_invalide_replique_sur_le_xff(self):
        headers = {
            "X-Real-IP": "pas-une-ip",
            "X-Forwarded-For": "203.0.113.99, 88.183.70.217",
        }
        assert resolve_client_ip(headers) == "88.183.70.217"

    def test_aucun_entete_renvoie_none(self):
        assert resolve_client_ip({}) is None
        assert resolve_client_ip(None) is None

    def test_entetes_vides_renvoient_none(self):
        assert resolve_client_ip({"X-Real-IP": "", "X-Forwarded-For": ""}) is None

    def test_xff_termine_par_une_videur(self):
        headers = {"X-Forwarded-For": "88.183.70.217, "}
        assert resolve_client_ip(headers) == "88.183.70.217"

    def test_ipv6_valide(self):
        assert resolve_client_ip({"X-Real-IP": "2001:db8::1"}) == "2001:db8::1"

    def test_ipv6_dans_le_xff(self):
        headers = {"X-Forwarded-For": "2001:db8::99, 2001:db8::1"}
        assert resolve_client_ip(headers) == "2001:db8::1"

    def test_adresse_invalide_renvoie_none(self):
        assert resolve_client_ip({"X-Real-IP": "999.1.1.1"}) is None

    def test_adresse_avec_port_renvoie_none(self):
        assert resolve_client_ip({"X-Real-IP": "203.0.113.7:54321"}) is None


class TestParseWhitelist:
    def test_adresse_seule(self):
        assert parse_whitelist(["192.0.2.1"]) == parse_whitelist(["192.0.2.1/32"])

    def test_cidr(self):
        assert len(parse_whitelist(["192.0.2.0/24", "2001:db8::/32"])) == 2

    def test_entrees_vides_ignorees(self):
        assert parse_whitelist(["", "  ", "192.0.2.1"]) == parse_whitelist(
            ["192.0.2.1"]
        )

    def test_entree_invalide_leve_une_erreur(self):
        with pytest.raises(ValueError, match="192.0.2.0/33"):
            parse_whitelist(["192.0.2.1", "192.0.2.0/33"])

    def test_entree_invalide_n_est_pas_ignoree_silencieusement(self):
        with pytest.raises(ValueError):
            parse_whitelist(["pas-un-cidr"])

    def test_liste_blanche_vide_renvoyee_vide(self):
        # Cas d'une variable d'environnement non renseignee : "".split(",")
        # donne [""] et ne doit produire ni erreur ni entree.
        assert parse_whitelist([""]) == ()
        assert parse_whitelist(["", "  "]) == ()

    def test_erreur_nomme_l_entree_et_sa_raison(self):
        with pytest.raises(ValueError) as excinfo:
            parse_whitelist(["192.0.2.0/33"])
        message = str(excinfo.value)
        assert "192.0.2.0/33" in message
        assert "IPv4 or IPv6 network" in message

    def test_entree_malformee_presente_entre_deux_valides(self):
        with pytest.raises(ValueError, match="192.0.2.1/24"):
            parse_whitelist(["192.0.2.1", "192.0.2.1/24", "2001:db8::/32"])


class TestIsWhitelisted:
    def test_ip_dans_le_cidr(self):
        whitelist = parse_whitelist(["192.0.2.0/24"])
        assert is_whitelisted("192.0.2.55", whitelist) is True

    def test_ip_hors_du_cidr(self):
        whitelist = parse_whitelist(["192.0.2.0/24"])
        assert is_whitelisted("198.51.100.55", whitelist) is False

    def test_ip_seule_dans_la_liste(self):
        whitelist = parse_whitelist(["192.0.2.1"])
        assert is_whitelisted("192.0.2.1", whitelist) is True
        assert is_whitelisted("192.0.2.2", whitelist) is False

    def test_ipv6_dans_le_cidr(self):
        whitelist = parse_whitelist(["2001:db8::/32"])
        assert is_whitelisted("2001:db8::42", whitelist) is True
        assert is_whitelisted("2001:dba::42", whitelist) is False

    def test_liste_blanche_vide(self):
        assert is_whitelisted("192.0.2.1", parse_whitelist([])) is False

    def test_ipv4_n_est_pas_dans_un_reseau_ipv6(self):
        whitelist = parse_whitelist(["2001:db8::/32"])
        assert is_whitelisted("192.0.2.1", whitelist) is False

    def test_adresse_invalide(self):
        whitelist = parse_whitelist(["192.0.2.0/24"])
        assert is_whitelisted("pas-une-ip", whitelist) is False

    def test_adresse_vide(self):
        whitelist = parse_whitelist(["192.0.2.0/24"])
        assert is_whitelisted("", whitelist) is False


class TestShouldIgnorePath:
    def test_asset_static_ignore(self):
        assert should_ignore_path("/static/js/node_modules/parseuri/index.js") is True

    def test_source_map_ignore(self):
        assert should_ignore_path("/static/js/socket.io.js.map") is True

    def test_fichier_static_avec_query_string_ignore(self):
        assert should_ignore_path("/static/js/app.js?v=3f8a1c") is True

    def test_chemin_static_exact_ignore(self):
        assert should_ignore_path("/static") is True

    def test_prefixe_trompeur_non_ignore(self):
        assert should_ignore_path("/staticx/js/app.js") is False

    def test_chemin_hors_static_non_ignore(self):
        assert should_ignore_path("/wp-login.php") is False

    def test_api_non_ignore(self):
        assert should_ignore_path("/api/config") is False

    def test_chemin_vide_ou_none(self):
        assert should_ignore_path("") is False
        assert should_ignore_path(None) is False


class TestRegisterHit:
    def test_premier_hit(self):
        hits = {}
        assert register_hit(hits, "192.0.2.1", 1000.0, window=10.0) == 1

    def test_trois_hits_dans_la_fenetre_franchissent_le_seuil(self):
        hits = {}
        counts = [
            register_hit(hits, "192.0.2.1", t, 10.0)
            for t in (1000.0, 1001.0, 1002.0)
        ]
        assert counts == [1, 2, 3]
        assert max(counts) >= 3

    def test_trois_hits_sur_une_heure_ne_franchissent_pas(self):
        hits = {}
        counts = [
            register_hit(hits, "192.0.2.1", t, 10.0)
            for t in (1000.0, 2000.0, 3000.0)
        ]
        assert counts == [1, 1, 1]
        assert max(counts) < 3

    def test_la_fenetre_glisse(self):
        hits = {}
        assert register_hit(hits, "192.0.2.1", 1000.0, 10.0) == 1
        assert register_hit(hits, "192.0.2.1", 1005.0, 10.0) == 2
        assert register_hit(hits, "192.0.2.1", 1020.0, 10.0) == 1

    def test_borne_inferieure_de_la_fenetre_incluse(self):
        hits = {}
        register_hit(hits, "192.0.2.1", 1000.0, 10.0)
        assert register_hit(hits, "192.0.2.1", 1010.0, 10.0) == 2

    def test_les_ips_sont_independantes(self):
        hits = {}
        register_hit(hits, "192.0.2.1", 1000.0, 10.0)
        register_hit(hits, "192.0.2.1", 1001.0, 10.0)
        assert register_hit(hits, "198.51.100.1", 1001.0, 10.0) == 1

    def test_le_dictionnaire_est_modifie_en_place(self):
        hits = {}
        register_hit(hits, "192.0.2.1", 1000.0, 10.0)
        register_hit(hits, "192.0.2.1", 1005.0, 10.0)
        assert hits == {"192.0.2.1": [1000.0, 1005.0]}

    def test_les_timestamps_hors_fenetre_sont_retires(self):
        hits = {}
        register_hit(hits, "192.0.2.1", 1000.0, 10.0)
        register_hit(hits, "192.0.2.1", 1001.0, 10.0)
        register_hit(hits, "192.0.2.1", 1020.0, 10.0)
        assert hits == {"192.0.2.1": [1020.0]}

    def test_rafale_du_scanner_mesuree(self):
        hits = {}
        counts = [
            register_hit(hits, "212.28.181.217", t, 10.0)
            for t in (1000.0, 1000.4, 1001.2)
        ]
        assert counts == [1, 2, 3]

    def test_la_memoire_croit_seulement_avec_les_ips_qui_ont_strike(self):
        hits = {}
        assert hits == {}
        register_hit(hits, "192.0.2.1", 1000.0, 10.0)
        assert list(hits) == ["192.0.2.1"]


class TestBanDuration:
    def test_premier_bannissement(self):
        assert ban_duration(1) == timedelta(hours=1)

    def test_serie_complete(self):
        assert ban_duration(1) == timedelta(hours=1)
        assert ban_duration(2) == timedelta(hours=4)
        assert ban_duration(3) == timedelta(hours=16)
        assert ban_duration(4) == timedelta(hours=64)
        assert ban_duration(5) == timedelta(hours=256)

    def test_croissance_par_carre(self):
        durations = [ban_duration(n).total_seconds() for n in range(1, 6)]
        assert durations == [durations[0] * 4**n for n in range(5)]

    def test_base_personnalisee(self):
        assert ban_duration(1, base_seconds=60) == timedelta(minutes=1)
        assert ban_duration(2, base_seconds=60) == timedelta(minutes=4)

    def test_base_par_defaut(self):
        assert ban_duration(1) == timedelta(seconds=BAN_BASE_SECONDS)

    def test_aucun_plafond(self):
        assert ban_duration(10) > timedelta(days=365 * 29)

    def test_sature_a_la_limite_de_timedelta(self):
        assert ban_duration(19) == timedelta(seconds=BAN_MAX_SECONDS)
        assert ban_duration(500) == timedelta(seconds=BAN_MAX_SECONDS)

    def test_numeros_invalides(self):
        with pytest.raises(ValueError, match="ban_count"):
            ban_duration(0)
        with pytest.raises(ValueError, match="ban_count"):
            ban_duration(-1)