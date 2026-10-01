import ipaddress
from collections.abc import Iterable, Mapping
from datetime import timedelta

BAN_BASE_SECONDS = 3600

# `timedelta` sature à 999 999 999 jours : la serie reste non bornee en
# theorie, mais sa representation s'arrete au 19e bannissement.
BAN_MAX_SECONDS = 999_999_999 * 86400

IGNORED_PATHS = frozenset({"/static"})
IGNORED_PATH_PREFIXES = ("/static/",)


def resolve_client_ip(headers: Mapping[str, str] | None) -> str | None:
    """
    Détermine l'adresse IP du client derrière le reverse proxy Scalingo.

    Scalingo ajoute sa propre adresse à la fin du `X-Forwarded-For` et écrase
    `X-Real-IP`, qui est donc la source la plus fiable. Les en-têtes sont
    insensibles à la casse. Un en-tête mal formé est ignoré plutôt que
    fatal : on préfère ne rien compter (fail-open) plutôt que bloquer tout
    le trafic.

    `request.remote_addr` n'est jamais utilisé : c'est une adresse interne
    (`10.0.0.x`) partagée par tous les dynos, elle ne distingue pas les
    clients.

    Args:
        headers: En-têtes de la requête (objet insensible à la casse de Flask,
            ou n'importe quel mapping)

    Returns:
        L'adresse IP normalisée, ou None si aucune en-tête exploitable
    """
    if not headers:
        return None

    normalized = {str(key).lower(): value for key, value in headers.items()}

    candidates = []
    real_ip = normalized.get("x-real-ip")

    if real_ip:
        candidates.append(str(real_ip).strip())

    forwarded_for = normalized.get("x-forwarded-for")

    if forwarded_for:
        chain = [part.strip() for part in str(forwarded_for).split(",") if part.strip()]
        # On ne prend que la droite de la chaîne : l'attaquant ne peut que
        # préfixer des valeurs, jamais suffixer les siennes après Scalingo.
        if chain:
            candidates.append(chain[-1])

    for candidate in candidates:
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            continue

    return None


def parse_whitelist(entries: Iterable[str]) -> tuple[object, ...]:
    """
    Convertit une liste d'entrées de liste blanche en réseaux ipaddress.

    Une entrée peut être une IP seule (`192.0.2.1`, réseau `192.0.2.1/32`
    implicite) ou un CIDR (`192.0.2.0/24`, `2001:db8::/32`).

    Une entrée invalide lève une erreur au démarrage plutôt que d'être ignorée
    silencieusement : une liste blanche tronquée est le moyen de se bannir
    soi-même.

    Args:
        entries: Entrées brutes, séparées par des virgules si elles viennent
            d'une variable d'environnement

    Returns:
        Tuple de réseaux prêts pour `is_whitelisted`
    """
    networks = []
    for raw_entry in entries:
        entry = str(raw_entry).strip()
        if not entry:
            continue
        try:
            networks.append(ipaddress.ip_network(entry))
        except ValueError as e:
            raise ValueError(
                f"Entrée invalide dans la liste blanche d'IP : {entry!r} ({e})"
            ) from e

    return tuple(networks)


def is_whitelisted(ip: str, whitelist: Iterable[object]) -> bool:
    """
    Indique si une IP appartient à un réseau de la liste blanche.

    Args:
        ip: Adresse IP normalisée
        whitelist: Réseaux issus de `parse_whitelist`

    Returns:
        True si l'IP est en liste blanche, False sinon ou si l'IP est invalide
    """
    if not ip:
        return False
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False

    return any(address in network for network in whitelist)


def should_ignore_path(path: str | None) -> bool:
    """
    Indique si un chemin doit être exclu du comptage des 404.

    Les fichiers servis par Flask sous `/static/` sont fournis sans
    contrainte (le client peut demander n'importe quel nom), donc un 404
    `/static/...` ne prouve pas du tout une intention malveillante. Les
    assets front sont stables et ne changent pas de nom entre deux requêtes.

    Args:
        path: Chemin de la requête, avec ou sans query string

    Returns:
        True si le chemin est ignoré
    """
    if not path:
        return False
    normalized = path.split("?", 1)[0]

    return normalized in IGNORED_PATHS or normalized.startswith(IGNORED_PATH_PREFIXES)


def register_hit(
    hits: dict[str, list[float]],
    ip: str,
    now: float,
    window: float,
) -> int:
    """
    Enregistre un 404 pour une IP et renvoie le nombre de hits dans la fenêtre.

    Fenêtre glissante : les timestamps plus vieux que `now - window` sont
    retirés avant le comptage. Le dictionnaire `hits` est modifié en place et
    fourni par l'appelant, ce qui évite un état global implicite.

    Une IP qui ne produit plus de 404 reste dans `hits` : le dictionnaire est
    donc borné par le nombre d'IP distinctes ayant déjà fait un 404, jamais
    purgé.

    Args:
        hits: Timestamps des 404 par IP, muté en place
        ip: Adresse IP normalisée
        now: Timestamp courant (epoch, en secondes)
        window: Durée de la fenêtre glissante, en secondes

    Returns:
        Nombre de hits de cette IP dans la fenêtre, `now` compris. La
        comparaison au seuil relève de l'appelant.
    """
    timestamps = hits.setdefault(ip, [])
    cutoff = now - window
    timestamps[:] = [timestamp for timestamp in timestamps if timestamp >= cutoff]
    timestamps.append(now)

    return len(timestamps)


def ban_duration(ban_count: int, base_seconds: int = BAN_BASE_SECONDS) -> timedelta:
    """
    Durée du bannissement pour un numéro de bannissement donné.

    Croissance par carré de l'exposant : le premier bannissement dure
    `base_seconds`, puis la durée est multipliée par 4 à chaque reincidence
    (1 h, 4 h, 16 h, 64 h, 256 h, 1 024 h...).

    Aucun plafond n'est appliqué, la seule limite est celle de la
    représentation : au-delà du 19e bannissement la durée sature à
    `BAN_MAX_SECONDS` (~2,7 millions d'années).

    Args:
        ban_count: Numéro du bannissement, à partir de 1
        base_seconds: Durée du premier bannissement

    Returns:
        Durée du bannissement
    """
    if ban_count < 1:
        raise ValueError(f"ban_count doit être >= 1, reçu {ban_count}")
    seconds = base_seconds * (2 ** (ban_count - 1)) ** 2

    return timedelta(seconds=min(seconds, BAN_MAX_SECONDS))
