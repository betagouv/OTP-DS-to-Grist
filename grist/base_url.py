"""Liste blanche des instances Grist vers lesquelles l'application peut appeler.

Toute communication avec Grist passe par une URL de base enregistrée dans
`otp_configurations.grist_base_url`, ou dérivée d'une page hébergée par une
instance Grist. Cette URL désigne une destination réseau : la restreindre à une
liste déclarée par l'exploitation évite qu'un champ de formulaire, ou une
valeur enregistrée ailleurs, ne dirige la clé d'API vers une adresse non
prévue.

La liste est déclarée par la variable d'environnement
`GRIST_BASE_URL_WHITELIST` (constante `utils.constants`), sous forme de
domaines séparés par des virgules. Une entrée ne décrit qu'un domaine : le
schéma, le port et le chemin sont ignorés, ce qui permet d'écrire aussi bien
`grist.exemple.fr` que l'URL complète d'une instance.

Une entrée peut être un joker (`*.gouv.fr`) : elle couvre alors tous les
sous-domaines du suffixe, pas le suffixe lui-même.
"""

from collections.abc import Iterable
from urllib.parse import urlsplit

from utils.constants import GRIST_BASE_URL_WHITELIST

# Préfixe d'une entrée joker : « *.suffixe » couvre tous les sous-domaines de
# « suffixe ».
WILDCARD_PREFIX = "*."


class GristBaseUrlNotAllowedError(ValueError):
    """L'URL de base Grist ne désigne pas une instance autorisée."""


class GristBaseUrlImmutableError(ValueError):
    """Tentative de modification de l'URL de base d'une configuration."""


def normalize_base_url(url: str | None) -> str:
    """
    Extrait l'hôte d'une URL de base Grist, en minuscules.

    Le schéma, le port et le chemin sont ignorés : deux écritures de la même
    instance (`https://grist.exemple.fr/api`,
    `http://grist.exemple.fr:8484/o/docs/api`) donnent le même hôte. Un point
    final de qualification (`grist.exemple.fr.`) est retiré.
    """
    candidate = str(url or "").strip()

    if not candidate:
        return ""

    # `urlsplit` n'interprète un nom de domaine nu que s'il est précédé de « // ».
    if "://" not in candidate:
        candidate = f"//{candidate}"

    return (urlsplit(candidate).hostname or "").strip(".").lower()


def parse_base_url_whitelist(entries: Iterable[str]) -> tuple[str, ...]:
    """
    Convertit une liste d'entrées de liste blanche en hôtes normalisés.

    Une entrée peut être un domaine nu (`grist.exemple.fr`), une URL complète
    (`https://grist.exemple.fr/api`) ou un joker (`*.gouv.fr`).

    Une entrée vide est ignorée : une virgule en trop dans la variable
    d'environnement ne doit pas faire échouer le chargement.

    Une entrée mal formée lève une erreur au démarrage plutôt que d'être ignorée
    silencieusement : une liste blanche mal interprétée autorise moins
    d'instances que prévu, et l'erreur ne se verrait qu'au moment de
    synchroniser.
    """
    hosts: list[str] = []
    for raw_entry in entries:
        entry = str(raw_entry).strip()
        if not entry:
            continue

        if entry.startswith(WILDCARD_PREFIX):
            suffix = normalize_base_url(entry[len(WILDCARD_PREFIX) :])
            if not suffix:
                raise ValueError(
                    "Joker invalide dans GRIST_BASE_URL_WHITELIST : "
                    f"{entry!r} (attendu « *.domaine »)"
                )
            hosts.append(f"{WILDCARD_PREFIX}{suffix}")
            continue

        if entry == "*":
            raise ValueError(
                f"Joker invalide dans GRIST_BASE_URL_WHITELIST : {entry!r} "
                "(attendu « *.domaine »)"
            )

        host = normalize_base_url(entry)
        if not host:
            raise ValueError(
                f"Entrée invalide dans GRIST_BASE_URL_WHITELIST : {entry!r} "
                "(aucun domaine exploitable)"
            )
        hosts.append(host)

    return tuple(hosts)


# Liste blanche effectivement appliquée, analysée une seule fois au chargement
# du module : une valeur d'environnement invalide échoue au démarrage de
# l'application, pas au premier appel vers Grist.
BASE_URL_WHITELIST: tuple[str, ...] = parse_base_url_whitelist(
    GRIST_BASE_URL_WHITELIST.split(",")
)


def is_base_url_allowed(
    url: str | None, whitelist: Iterable[str] | None = None
) -> bool:
    """
    Indique si une URL de base désigne une instance autorisée.

    Une URL est autorisée si son hôte est listé tel quel, ou si un joker
    `*.suffixe` de la liste couvre cet hôte : `*.gouv.fr` couvre
    `grist.numerique.gouv.fr`, mais ni `gouv.fr` ni `gouv.fr.evil.example`.
    """
    allowed = BASE_URL_WHITELIST if whitelist is None else whitelist

    host = normalize_base_url(url)
    if not host:
        return False

    for entry in allowed:
        if entry.startswith(WILDCARD_PREFIX):
            if host.endswith(f".{entry[len(WILDCARD_PREFIX) :]}"):
                return True
        elif host == entry:
            return True

    return False


def assert_base_url_allowed(
    url: str | None, whitelist: Iterable[str] | None = None
) -> None:
    """
    Vérifie qu'une URL de base est autorisée, ou lève une erreur.
    """
    if is_base_url_allowed(url, whitelist):
        return

    host = normalize_base_url(url) or "(vide)"
    raise GristBaseUrlNotAllowedError(
        f"URL de base Grist non autorisée : {host}"
    )
