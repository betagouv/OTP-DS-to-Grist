"""
Comptes de service Grist pour les configurations utilisateur.

Une clé API de compte de service est utilisée telle quelle. Si c'est une clé
d'utilisateur qui est fournie, un compte de service est créé à son nom, attaché
au document en propriétaire (`owners`), et sa clé est utilisée à la place :
la synchronisation exige le niveau `owners`, que la clé utilisateur peut
transmettre au document mais que l'on préfère ne pas stocker en base.
"""

import datetime as dt
from dataclasses import dataclass

from requests.exceptions import HTTPError

from grist.client import GristClient
from grist.utils import GRIST_OWNER_ACCESS, require_owner_access

# TLD des logins des comptes de service Grist (Login.SERVICE_ACCOUNTS_TLD dans
# grist-core) : un profil dont l'email se termine par ce TLD est un compte de
# service, pas un utilisateur.
SERVICE_ACCOUNTS_TLD = "serviceaccounts.invalid"

# Préfixe du libellé des comptes de service créés, pour les rapprocher de
# l'utilisateur Grist propriétaire de la clé fournie.
SERVICE_ACCOUNT_LABEL_PREFIX = "OTP-DS-to-Grist"

# Message affiché quand l'instance Grist n'a pas activé les comptes de service.
SERVICE_ACCOUNTS_DISABLED_MESSAGE = (
    "Les comptes de service ne sont pas activés sur cette instance Grist : "
    "fournissez une clé de compte de service, ou activez "
    "GRIST_ENABLE_SERVICE_ACCOUNTS côté serveur."
)

# Message affiché quand la clé est celle d'un compte de service expiré
# (Grist répond 401 « Service Account has expired »).
SERVICE_ACCOUNT_EXPIRED_MESSAGE = (
    "Le compte de service Grist a expiré (péremption atteinte) : "
    "créez-en un nouveau ou renouvelez son expiration."
)


class ServiceAccountsNotEnabledError(Exception):
    """L'instance Grist cible n'a pas activé les comptes de service."""


@dataclass
class ResolvedGristKey:
    """Clé API Grist à stocker en configuration, et son propriétaire."""

    api_key: str
    owner_email: str | None
    service_account_created: bool


def is_service_account_email(email: str | None) -> bool:
    """Si l'email du profil Grist est celui d'un compte de service."""
    return bool(email) and email.lower().endswith(f"@{SERVICE_ACCOUNTS_TLD}")


def service_account_expires_at(today: dt.date | None = None) -> str:
    """
    Péremption du compte de service : premier jour du même mois, l'année
    suivante (ex. créé le 2026-11-26 -> 2027-11-01), en ISO 8601 UTC.
    """
    today = today or dt.date.today()
    expiry = dt.date(today.year + 1, today.month, 1)

    return f"{expiry.isoformat()}T00:00:00.000Z"


def is_service_account_key(base_url: str, api_key: str) -> bool:
    """Si la clé API appartient à un compte de service (email du profil)."""
    return is_service_account_email(
        GristClient(base_url, api_key).get_grist_user_email()
    )


def service_accounts_usable(base_url: str, api_key: str) -> bool:
    """
    Si une clé utilisateur pourra être remplacée par un compte de service sur
    cette instance : toujours oui pour une clé de compte de service, sinon
    seulement si l'instance active les comptes de service (sonde en lecture,
    aucun compte créé).
    """
    client = GristClient(base_url, api_key)
    if is_service_account_email(client.get_grist_user_email()):
        return True

    return client.service_accounts_enabled()


def resolve_grist_api_key(base_url: str, api_key: str, doc_id: str) -> ResolvedGristKey:
    """
    Clé API Grist à stocker pour la configuration.

    Une clé de compte de service est retournée telle quelle. Pour une clé
    d'utilisateur, le document doit être en accès `owners` (seul niveau
    permettant d'y attacher un compte de service), puis un compte de service
    est créé, attaché au document en `owners`, et sa clé est retournée.
    """
    client = GristClient(base_url, api_key, doc_id)
    email = client.get_profile().get("email")

    if is_service_account_email(email):
        # Clé de compte de service fournie telle quelle : elle doit quand même
        # avoir accès propriétaire au document, sinon la config serait
        # enregistrée avec une clé inutilisable.
        require_owner_access(base_url, api_key, doc_id)
        return ResolvedGristKey(api_key, email, service_account_created=False)

    require_owner_access(base_url, api_key, doc_id)

    today = dt.date.today()
    label = f"{SERVICE_ACCOUNT_LABEL_PREFIX} — {email or 'utilisateur inconnu'}"
    description = f"Document {doc_id}, créé le {today.isoformat()}"
    expires_at = service_account_expires_at(today)

    try:
        created = client.create_service_account(label, description, expires_at)
    except HTTPError as error:
        if error.response is not None and error.response.status_code == 404:
            raise ServiceAccountsNotEnabledError(
                SERVICE_ACCOUNTS_DISABLED_MESSAGE
            ) from error
        raise

    client.update_doc_access({created["login"]: GRIST_OWNER_ACCESS})

    return ResolvedGristKey(created["key"], email, service_account_created=True)
