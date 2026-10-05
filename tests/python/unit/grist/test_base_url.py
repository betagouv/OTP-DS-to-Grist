import pytest

from grist import base_url
from grist.base_url import (
    BASE_URL_WHITELIST,
    GristBaseUrlImmutableError,
    GristBaseUrlNotAllowedError,
    assert_base_url_allowed,
    is_base_url_allowed,
    normalize_base_url,
    parse_base_url_whitelist,
)

# Instances Grist réellement utilisées en production, relevées dans les
# configurations existantes. Cette liste sert de référence : toute nouvelle
# instance déployée doit être ajoutée ici, et la liste blanche de production
# (WHITELIST_PRODUCTION) doit être revue en conséquence.
URLS_PRODUCTION: tuple[str, ...] = (
    "https://dleges.getgrist.com/api",
    "https://grist.dataregion.fr/o/ditp-piapi/api",
    "https://grist.dataregion.fr/o/docs/api",
    "https://grist.dataregion.fr/o/draaf-bretagne-sg/api",
    "https://grist.dataregion.fr/o/draaf-bretagne-srafob/api",
    "https://grist.dataregion.fr/o/draafsral/api",
    "https://grist.dataregion.fr/o/enseignement-agricole/api",
    "https://grist.dataregion.fr/o/pfra-bzh/api",
    "https://grist.dataregion.fr/o/srefaa/api",
    "https://grist.incubateur.anct.gouv.fr/o/anct/api",
    "https://grist.incubateur.anct.gouv.fr/o/docs/api",
    "https://grist.incubateur.dnum.din.developpement-durable.gouv.fr/o/amidomar/api",
    "https://grist.incubateur.dnum.din.developpement-durable.gouv.fr/o/docs/api",
    "https://grist.numerique.gouv.fr",
    "https://grist.numerique.gouv.fr/api",
    "https://grist.numerique.gouv.fr/o/ac-dombasle/api",
    "https://grist.numerique.gouv.fr/o/adn/api",
    "https://grist.numerique.gouv.fr/o/agir-numerique/api",
    "https://grist.numerique.gouv.fr/o/agir-rh/api",
    "https://grist.numerique.gouv.fr/o/approbiom/api",
    "https://grist.numerique.gouv.fr/o/baj/api",
    "https://grist.numerique.gouv.fr/o/bbp/api",
    "https://grist.numerique.gouv.fr/o/bilan/api",
    "https://grist.numerique.gouv.fr/o/bnssa73/api",
    "https://grist.numerique.gouv.fr/o/cdcs/api",
    "https://grist.numerique.gouv.fr/o/cesan-investigation/api",
    "https://grist.numerique.gouv.fr/o/ciostrasbourg/api",
    "https://grist.numerique.gouv.fr/o/ddfip19sfdl/api",
    "https://grist.numerique.gouv.fr/o/ddt31-sea/api",
    "https://grist.numerique.gouv.fr/o/ddt84-sct/api",
    "https://grist.numerique.gouv.fr/o/demarchenumerique/api",
    "https://grist.numerique.gouv.fr/o/devops2025/api",
    "https://grist.numerique.gouv.fr/o/dgitm-sfg4-surete-transports/api",
    "https://grist.numerique.gouv.fr/o/disi-co-rh/api",
    "https://grist.numerique.gouv.fr/o/docs/api",
    "https://grist.numerique.gouv.fr/o/draaf-aura-ag/api",
    "https://grist.numerique.gouv.fr/o/drajesna-fce/api",
    "https://grist.numerique.gouv.fr/o/drane/api",
    "https://grist.numerique.gouv.fr/o/drane-clermont/api",
    "https://grist.numerique.gouv.fr/o/drealcvlsebrinal/api",
    "https://grist.numerique.gouv.fr/o/ensfea-moow/api",
    "https://grist.numerique.gouv.fr/o/ensfea-ri/api",
    "https://grist.numerique.gouv.fr/o/fdfen73/api",
    "https://grist.numerique.gouv.fr/o/fhapaca/api",
    "https://grist.numerique.gouv.fr/o/formation-bloc2-ensfea/api",
    "https://grist.numerique.gouv.fr/o/fpca/api",
    "https://grist.numerique.gouv.fr/o/fsaoccitanie/api",
    "https://grist.numerique.gouv.fr/o/gaz/api",
    "https://grist.numerique.gouv.fr/o/gcoc/api",
    "https://grist.numerique.gouv.fr/o/gomonc/api",
    "https://grist.numerique.gouv.fr/o/gqddtm11/api",
    "https://grist.numerique.gouv.fr/o/gristotheque-pays-de-la-loire/api",
    "https://grist.numerique.gouv.fr/o/gvol/api",
    "https://grist.numerique.gouv.fr/o/hse/api",
    "https://grist.numerique.gouv.fr/o/inclusion/api",
    "https://grist.numerique.gouv.fr/o/indemntub/api",
    "https://grist.numerique.gouv.fr/o/isn/api",
    "https://grist.numerique.gouv.fr/o/ksp/api",
    "https://grist.numerique.gouv.fr/o/lab-section-te/api",
    "https://grist.numerique.gouv.fr/o/ldmems/api",
    "https://grist.numerique.gouv.fr/o/marvin/api",
    "https://grist.numerique.gouv.fr/o/one-trick-pony/api",
    "https://grist.numerique.gouv.fr/o/paye-dombasle/api",
    "https://grist.numerique.gouv.fr/o/pdl-hydro/api",
    "https://grist.numerique.gouv.fr/o/piapi/api",
    "https://grist.numerique.gouv.fr/o/pifag/api",
    "https://grist.numerique.gouv.fr/o/pony-express/api",
    "https://grist.numerique.gouv.fr/o/rsm2search/api",
    "https://grist.numerique.gouv.fr/o/sdei31/api",
    "https://grist.numerique.gouv.fr/o/sraa/api",
    "https://grist.numerique.gouv.fr/o/sraa-occitanie/api",
    "https://grist.numerique.gouv.fr/o/sral-planification/api",
    "https://grist.numerique.gouv.fr/o/srfd-occ/api",
    "https://grist.numerique.gouv.fr/o/srfd-occitanie/api",
    "https://grist.numerique.gouv.fr/o/suivi-eleves-guillaumin/api",
    "https://grist.numerique.gouv.fr/o/tableaudesuivi2026/api",
    "https://grist.numerique.gouv.fr/o/testdb/api",
    "https://grist.numerique.gouv.fr/o/upsaclay-dma/api",
    "https://grist.numerique.gouv.fr/o/uvet/api",
    "https://grist.toutatice.fr/o/docs/api",
    "https://grist.toutatice.fr/o/drasi/api",
    "https://igrist.sdis66.fr/o/ressourceshumaines/api",
)

# Les 7 domaines qui hébergent ces instances.
DOMAINES_PRODUCTION: frozenset[str] = frozenset(
    {
        "dleges.getgrist.com",
        "grist.dataregion.fr",
        "grist.incubateur.anct.gouv.fr",
        "grist.incubateur.dnum.din.developpement-durable.gouv.fr",
        "grist.numerique.gouv.fr",
        "grist.toutatice.fr",
        "igrist.sdis66.fr",
    }
)

# Liste blanche de production recommandée : un joker pour tous les services de
# l'État, un domaine pour chaque hébergeur extérieur à gouv.fr.
WHITELIST_PRODUCTION: tuple[str, ...] = (
    "*.gouv.fr",
    "dleges.getgrist.com",
    "grist.dataregion.fr",
    "grist.toutatice.fr",
    "igrist.sdis66.fr",
)

# Même périmètre sans joker, pour vérifier que les 7 domaines sont énumérés
# explicitement et qu'aucun ne dépend du joker.
WHITELIST_PRODUCTION_SANS_JOKER: tuple[str, ...] = tuple(sorted(DOMAINES_PRODUCTION))

# Domaines voisins des domaines de production, hors gouv.fr : doivent tous rester
# refusés. `numerique.gouv.fr` en est absent car c'est un sous-domaine de gouv.fr,
# voir TestListeDeProduction.test_joker_gouv_couvre_tout_sous_domaine_gouv_fr.
DOMAINES_VOISINS: tuple[str, ...] = (
    "gouv.fr",
    "dataregion.fr",
    "getgrist.com",
    "toutatice.fr",
    "sdis66.fr",
)


class TestNormalizeBaseUrl:
    def test_url_complete(self):
        assert normalize_base_url("https://grist.exemple.fr/api") == "grist.exemple.fr"

    def test_domaine_sans_schema(self):
        assert normalize_base_url("grist.exemple.fr") == "grist.exemple.fr"

    def test_port_et_chemin_ignores(self):
        assert (
            normalize_base_url("http://grist.exemple.fr:8484/o/docs/api")
            == "grist.exemple.fr"
        )

    def test_minuscules_et_point_final(self):
        assert normalize_base_url("https://GRIST.Exemple.FR./api") == "grist.exemple.fr"

    def test_adresse_ipv6(self):
        assert normalize_base_url("http://[::1]:8484/api") == "::1"

    def test_adresse_ipv4(self):
        assert normalize_base_url("http://127.0.0.1:8484/api") == "127.0.0.1"

    def test_vide_renvoie_chaine_vide(self):
        assert normalize_base_url("") == ""
        assert normalize_base_url("   ") == ""
        assert normalize_base_url(None) == ""

    def test_sans_hote_renvoie_chaine_vide(self):
        assert normalize_base_url("http://") == ""


class TestParseBaseUrlWhitelist:
    def test_domaines_separes_par_une_virgule(self):
        entries = "grist.exemple.fr, igrist.autre.fr".split(",")

        assert parse_base_url_whitelist(entries) == (
            "grist.exemple.fr",
            "igrist.autre.fr",
        )

    def test_url_complete_reduite_a_son_hote(self):
        entries = ["https://grist.dataregion.fr/o/demarche/api"]

        assert parse_base_url_whitelist(entries) == ("grist.dataregion.fr",)

    def test_joker_conserve(self):
        assert parse_base_url_whitelist(["*.gouv.fr"]) == ("*.gouv.fr",)

    def test_entrees_vides_ignorees(self):
        entries = ["grist.exemple.fr", "", "   ", "igrist.autre.fr"]

        assert parse_base_url_whitelist(entries) == (
            "grist.exemple.fr",
            "igrist.autre.fr",
        )

    def test_liste_vide(self):
        assert parse_base_url_whitelist([]) == ()
        assert parse_base_url_whitelist([""]) == ()

    def test_entree_sans_domaine_leve_une_erreur(self):
        with pytest.raises(ValueError, match="GRIST_BASE_URL_WHITELIST"):
            parse_base_url_whitelist(["http://"])

    def test_joker_incomplet_leve_une_erreur(self):
        with pytest.raises(ValueError, match="GRIST_BASE_URL_WHITELIST"):
            parse_base_url_whitelist(["*."])

    def test_joker_unique_leve_une_erreur(self):
        with pytest.raises(ValueError, match="GRIST_BASE_URL_WHITELIST"):
            parse_base_url_whitelist(["*"])

    def test_erreur_cite_l_entree_fautive(self):
        with pytest.raises(ValueError, match="https://"):
            parse_base_url_whitelist(["https://"])


class TestIsBaseUrlAllowed:
    def test_hote_liste(self):
        whitelist = ("grist.exemple.fr",)

        assert is_base_url_allowed("https://grist.exemple.fr/api", whitelist) is True

    def test_hote_non_liste(self):
        whitelist = ("grist.exemple.fr",)

        assert is_base_url_allowed("https://grist.autre.fr/api", whitelist) is False

    def test_port_et_chemin_ignores(self):
        whitelist = ("grist.exemple.fr",)

        assert is_base_url_allowed("http://grist.exemple.fr:8484/o/x/api", whitelist)

    def test_casse_ignoree(self):
        whitelist = ("grist.exemple.fr",)

        assert is_base_url_allowed("https://GRIST.Exemple.FR/api", whitelist)

    def test_joker_couvre_un_sous_domaine(self):
        whitelist = ("*.gouv.fr",)
        url = "https://grist.incubateur.anct.gouv.fr/api"

        assert is_base_url_allowed(url, whitelist)

    def test_joker_ne_couvre_pas_le_suffixe_lui_meme(self):
        whitelist = ("*.gouv.fr",)

        assert is_base_url_allowed("https://gouv.fr/api", whitelist) is False

    def test_joker_ne_couvre_pas_un_domaine_qui_termine_par_le_suffixe(self):
        whitelist = ("grist.dataregion.fr",)
        url = "https://grist.dataregion.fr.evil.example/api"

        assert is_base_url_allowed(url, whitelist) is False

    def test_url_vide_refusee(self):
        assert is_base_url_allowed("", ("grist.exemple.fr",)) is False
        assert is_base_url_allowed(None, ("grist.exemple.fr",)) is False

    def test_liste_vide_refuse_tout(self):
        assert is_base_url_allowed("https://grist.exemple.fr/api", ()) is False

    def test_liste_par_defaut_issues_de_l_environnement(self, monkeypatch):
        monkeypatch.setattr(base_url, "BASE_URL_WHITELIST", ("grist.autorise.fr",))

        assert is_base_url_allowed("https://grist.autorise.fr/api") is True
        assert is_base_url_allowed("https://grist.autre.fr/api") is False


class TestAssertBaseUrlAllowed:
    def test_url_autorisee_ne_leve_rien(self):
        url = "https://grist.exemple.fr/api"

        assert assert_base_url_allowed(url, ("grist.exemple.fr",)) is None

    def test_url_refusee_leve_une_erreur(self):
        with pytest.raises(GristBaseUrlNotAllowedError):
            assert_base_url_allowed("https://grist.autre.fr/api", ("grist.exemple.fr",))

    def test_erreur_est_une_value_error(self):
        assert issubclass(GristBaseUrlNotAllowedError, ValueError)
        assert issubclass(GristBaseUrlImmutableError, ValueError)

    def test_message_nomme_l_hote_refuse_et_la_variable(self):
        with pytest.raises(GristBaseUrlNotAllowedError) as excinfo:
            assert_base_url_allowed(
                "https://grist.autre.fr/api", ("grist.exemple.fr",)
            )

        message = str(excinfo.value)
        assert "grist.autre.fr" in message
        assert "GRIST_BASE_URL_WHITELIST" in message

    def test_message_ne_révèle_pas_la_liste(self):
        with pytest.raises(GristBaseUrlNotAllowedError) as excinfo:
            assert_base_url_allowed(
                "https://grist.autre.fr/api", ("grist.exemple.fr",)
            )

        assert "grist.exemple.fr" not in str(excinfo.value)

    def test_url_vide_refusee(self):
        with pytest.raises(GristBaseUrlNotAllowedError, match="vide"):
            assert_base_url_allowed("", ("grist.exemple.fr",))


class TestBaseUrlWhitelist:
    def test_liste_de_l_environnement_est_analysee_au_chargement(self):
        assert isinstance(BASE_URL_WHITELIST, tuple)
        assert BASE_URL_WHITELIST
        assert "*.grist.com" in BASE_URL_WHITELIST

    def test_domaines_des_tests_sont_autorises(self):
        for url in (
            "https://grist.example.com/api",
            "https://test.grist.com/api",
            "https://grist.test",
            "https://grist.test.com/api",
            "https://grist.explicit.com/api",
            "https://grist.com/api",
            "https://grist.server.com/api",
            "https://grist.numerique.gouv.fr/api",
            "http://localhost:8484/o/docs/api",
            "http://127.0.0.1:8484/api",
        ):
            assert is_base_url_allowed(url), url

    def test_domaine_étranger_refusé(self):
        assert is_base_url_allowed("https://grist.evil.example/api") is False


class TestListeDeProduction:
    """Vérifie que la liste blanche de production couvre les instances déployées,
    et seulement elles."""

    @staticmethod
    def _urls_refusees(whitelist):
        return [
            url
            for url in URLS_PRODUCTION
            if not is_base_url_allowed(url, whitelist)
        ]

    def test_urls_de_production_autorisees(self):
        refusees = self._urls_refusees(WHITELIST_PRODUCTION)

        assert refusees == [], f"URLs de production refusées : {refusees}"

    def test_urls_de_production_autorisees_sans_joker(self):
        refusees = self._urls_refusees(WHITELIST_PRODUCTION_SANS_JOKER)

        assert refusees == [], f"URLs de production refusées : {refusees}"

    def test_liste_recommandee_enumere_les_domaines_hors_gouv(self):
        """La liste recommandée s'appuie sur `*.gouv.fr` : tout hébergeur hors
        gouv.fr doit être énuméré, sinon la liste pourrait être élargie à un
        joker trop permissif (`*.fr`, `*`)."""
        hors_gouv = {
            domain for domain in DOMAINES_PRODUCTION if not domain.endswith(".gouv.fr")
        }

        assert hors_gouv == {
            "dleges.getgrist.com",
            "grist.dataregion.fr",
            "grist.toutatice.fr",
            "igrist.sdis66.fr",
        }
        assert hors_gouv <= set(WHITELIST_PRODUCTION)

    def test_domaines_de_production_autorises(self):
        for domain in DOMAINES_PRODUCTION:
            assert (
                is_base_url_allowed(f"https://{domain}/api", WHITELIST_PRODUCTION)
            ), domain

    def test_joker_gouv_couvre_tout_sous_domaine_gouv_fr(self):
        """Limite assumée du joker `*.gouv.fr` : tout sous-domaine de gouv.fr est
        autorisé, y compris en dehors des instances de production recensées, mais
        pas gouv.fr lui-même."""
        url = "https://numerique.gouv.fr/api"

        assert is_base_url_allowed(url, WHITELIST_PRODUCTION)
        assert not is_base_url_allowed(url, WHITELIST_PRODUCTION_SANS_JOKER)
        assert not is_base_url_allowed("https://gouv.fr/api", WHITELIST_PRODUCTION)

    def test_domaines_voisins_refuses(self):
        for domain in DOMAINES_VOISINS:
            url = f"https://{domain}/api"

            assert not is_base_url_allowed(url, WHITELIST_PRODUCTION), domain
            assert not is_base_url_allowed(url, WHITELIST_PRODUCTION_SANS_JOKER), domain

    def test_domaine_prolongant_un_domaine_autorise_refuse(self):
        # `grist.dataregion.fr.evil.example` ne doit pas être confondu avec
        # `grist.dataregion.fr` : la comparaison se fait sur l'hôte exact.
        url = "https://grist.dataregion.fr.evil.example/api"

        assert not is_base_url_allowed(url, WHITELIST_PRODUCTION)
        assert not is_base_url_allowed(url, WHITELIST_PRODUCTION_SANS_JOKER)

    def test_port_inhabituel_accepte(self):
        url = "https://igrist.sdis66.fr:8443/o/ressourceshumaines/api"

        assert is_base_url_allowed(url, WHITELIST_PRODUCTION)
        assert is_base_url_allowed(url, WHITELIST_PRODUCTION_SANS_JOKER)

    def test_garde_fou_nombre_de_domaines(self):
        """Une nouvelle instance de production non répertoriée ici doit faire
        échouer la suite : vérifier aussi que la liste des URLs ne contient que
        des domaines connus."""
        assert {normalize_base_url(url) for url in URLS_PRODUCTION} == set(
            DOMAINES_PRODUCTION
        )
