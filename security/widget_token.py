"""Vérification des jetons widget Grist.

Le widget Grist reçoit de Grist un jeton signé qui transporte l'identité
certifiée de l'utilisateur (`userId`, `docId`) et son droit d'écriture
(`readOnly`). Le backend ne peut pas vérifier cette signature hors ligne
(secret symétrique propre au document, pas de JWKS) : il la fait donc vérifier
par Grist, en présentant le jeton tel quel en paramètre `auth` d'un endpoint du
document.

La vérification réussie est mise en cache quelques dizaines de secondes : le
jeton est court (≈15 min) et les requêtes d'une même page partagent le même
jeton.
"""

import base64
import hashlib
import json
import time

import requests

from grist.base_url import assert_base_url_allowed

WIDGET_TOKEN_HEADER = "X-Grist-Widget-Token"
BASE_URL_HEADER = "X-Grist-Base-Url"

# Durée de mise en cache d'une vérification réussie, bornée par l'expiration
# du jeton (le jeton vit ≈15 min, bien plus que cette marge).
VALIDATION_CACHE_TTL_SECONDS = 60

# Timeout de l'appel de vérification vers Grist.
TOKEN_VALIDATION_TIMEOUT_SECONDS = 5

_TOKEN_CACHE: dict[str, tuple[dict, float]] = {}


class WidgetTokenError(Exception):
    """Erreur de base liée au jeton widget."""


class WidgetTokenInvalidError(WidgetTokenError):
    """Jeton absent, illisible, refusé par Grist, expiré ou d'un autre document."""


class WidgetTokenUnavailableError(WidgetTokenError):
    """Grist n'a pas pu vérifier le jeton (réseau, timeout, erreur serveur)."""


def extract_widget_token(headers) -> str | None:
    """Retourne le jeton widget présenté dans l'en-tête, ou None."""
    token = (headers.get(WIDGET_TOKEN_HEADER) or "").strip()

    return token or None


def decode_widget_token_identity(token: str) -> dict:
    """
    Lit l'identité portée par un jeton, sans vérifier sa signature.

    Sert uniquement à connaître le document visé pour construire l'appel de
    vérification ; la confiance n'est accordée qu'après validation par Grist.
    """
    try:
        payload = token.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)

        return json.loads(base64.urlsafe_b64decode(padded))
    except Exception as e:
        raise WidgetTokenInvalidError(f"Jeton widget illisible : {e}") from e


def validate_widget_token(token: str, base_url: str, doc_id: str) -> dict:
    """
    Fait vérifier un jeton widget par Grist et retourne son contenu.

    L'URL de base doit désigner une instance autorisée : elle vient de la base
    ou d'un formulaire, jamais d'une valeur permettant de joindre une adresse
    arbitraire. Le résultat est mis en cache quelques dizaines de secondes.
    """
    cache_key = _cache_key(token)
    cached = _TOKEN_CACHE.get(cache_key)
    if cached and cached[1] > time.time():
        return cached[0]

    assert_base_url_allowed(base_url)

    try:
        response = requests.get(
            f"{base_url.rstrip('/')}/docs/{doc_id}/tables",
            params={"auth": token},
            timeout=TOKEN_VALIDATION_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        raise WidgetTokenUnavailableError(f"Grist injoignable : {e}") from e

    if response.status_code in (401, 403):
        raise WidgetTokenInvalidError("Jeton widget refusé par Grist")

    if response.status_code >= 500:
        raise WidgetTokenUnavailableError(
            f"Grist a répondu {response.status_code}"
        )

    if response.status_code != 200:
        raise WidgetTokenInvalidError(
            f"Vérification refusée par Grist ({response.status_code})"
        )

    identity = decode_widget_token_identity(token)
    _store(cache_key, identity)

    return identity


def clear_validation_cache() -> None:
    """Vide le cache de vérification (tests, ou après une rotation de jeton)."""
    _TOKEN_CACHE.clear()


def _cache_key(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _cache_ttl(identity: dict) -> float:
    expiry = identity.get("exp")
    if isinstance(expiry, (int, float)):
        return max(0.0, min(VALIDATION_CACHE_TTL_SECONDS, expiry - time.time()))

    return VALIDATION_CACHE_TTL_SECONDS


def _store(cache_key: str, identity: dict) -> None:
    now = time.time()
    _TOKEN_CACHE[cache_key] = (identity, now + _cache_ttl(identity))

    for key, (_, expires_at) in list(_TOKEN_CACHE.items()):
        if expires_at <= now:
            del _TOKEN_CACHE[key]
