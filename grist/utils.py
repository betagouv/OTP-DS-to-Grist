"""
Utilitaires transverses propres à Grist.

Regroupe les règles imposées par Grist que plusieurs modules doivent appliquer
de manière identique, comme la construction des identifiants de colonnes et de
tables à partir des libellés Démarche Numérique, ou l'accès propriétaire exigé
de la clé API sur le document (seule règle de ce module qui interroge Grist).
"""

import hashlib
import re
import unicodedata
from typing import Any

from requests.exceptions import HTTPError

from grist.base_url import GristBaseUrlNotAllowedError
from grist.client import GristClient
from utils.log import log_error

# Seul niveau d'accès de la clé API qui permet de synchroniser : la
# synchronisation crée ou vide des tables (changement de structure), ce que
# Grist refuse aux éditeurs selon les paramètres d'accès du document.
GRIST_OWNER_ACCESS = "owners"

# Niveaux rendus par `key_access_level` hors niveaux Grist : clé sans accès au
# document, ou Grist injoignable (transitoire, à ne pas confondre avec un refus).
GRIST_KEY_NO_ACCESS = "no-access"
GRIST_KEY_ACCESS_UNAVAILABLE = "unavailable"


class GristKeyAccessError(Exception):
    """La clé API Grist ne permet pas de synchroniser le document."""


class GristKeyNoAccessError(GristKeyAccessError):
    """La clé API ne voit pas le document (401, 403 ou 404)."""

    def __init__(self) -> None:
        super().__init__("Clé API sans accès au document Grist")


class GristKeyInsufficientAccessError(GristKeyAccessError):
    """La clé API voit le document sans en être propriétaire."""

    def __init__(self, access_level: str | None) -> None:
        super().__init__("Accès propriétaire requis sur le document Grist")
        self.access_level = access_level


class GristUnavailableError(GristKeyAccessError):
    """Grist n'a pas donné de réponse exploitable : l'accès n'est pas vérifié."""

    def __init__(self) -> None:
        super().__init__("Grist indisponible")


def require_owner_access(base_url: str, api_key: str, doc_id: str) -> dict[str, Any]:
    """
    Informations du document, si la clé API en est propriétaire.

    Toute autre issue est un échec : niveau d'accès autre que `owners`,
    document invisible pour la clé, ou Grist sans réponse exploitable.
    """
    try:
        doc_info = GristClient(base_url, api_key, doc_id).get_document_info()
    except GristBaseUrlNotAllowedError:
        raise
    except HTTPError as error:
        status_code = (
            error.response.status_code if error.response is not None else None
        )
        if status_code in (401, 403, 404):
            raise GristKeyNoAccessError() from error
        raise GristUnavailableError() from error
    except Exception as error:
        raise GristUnavailableError() from error

    if not isinstance(doc_info, dict):
        raise GristUnavailableError()

    access_level = doc_info.get("access")
    if access_level != GRIST_OWNER_ACCESS:
        raise GristKeyInsufficientAccessError(access_level)

    return doc_info


def normalize_column_name(name: str | None, max_length: int = 150) -> str:
    """
    Normalise un libellé en identifiant valide pour Grist (colonne ou table).

    Le schéma, l'extraction des dossiers et l'écriture des blocs répétables
    doivent produire le même identifiant pour un même libellé : sinon les
    valeurs ne trouvent pas leur colonne et sont ignorées.
    """
    # Supprimer les espaces en début et fin, et remplacer les espaces consécutifs par un seul espace
    name = (name or "").strip()
    name = re.sub(r"\s+", " ", name)

    name = name.replace("'", "_")
    name = name.replace("`", "_")  # Accent grave utilisé comme apostrophe

    # Supprimer les numéros de début type "1. ", "2) ", etc.
    name = re.sub(r"^[\d]+[\.\)]\s*", "", name)

    # Supprimer les accents
    name = unicodedata.normalize("NFKD", name)
    name = "".join([c for c in name if not unicodedata.combining(c)])

    # Convertir en minuscules et remplacer les caractères non alphanumériques par des underscores
    name = name.lower()
    name = re.sub(r"[^a-z0-9_]", "_", name)

    # Éliminer les underscores multiples consécutifs
    name = re.sub(r"_+", "_", name)

    # Éliminer les underscores en début et fin
    name = name.strip("_")

    # Libellé vide ou sans aucun caractère exploitable
    if not name:
        return "column"

    # S'assurer que le nom commence par une lettre
    if not name[0].isalpha():
        name = "col_" + name

    # Tronquer si nécessaire à max_length caractères
    if len(name) > max_length:
        # Générer un hash pour garantir l'unicité
        hash_part = hashlib.md5(name.encode()).hexdigest()[:6]
        name = f"{name[: max_length - 7]}_{hash_part}"

    return name


def key_access_level(base_url: str, api_key: str, doc_id: str) -> str:
    """
    Niveau d'accès de la clé API sur le document, issu de `require_owner_access`.

    Rend `owners`, le niveau Grist d'une clé non propriétaire,
    `GRIST_KEY_NO_ACCESS` ou `GRIST_KEY_ACCESS_UNAVAILABLE`.
    """
    try:
        return require_owner_access(base_url, api_key, doc_id)["access"]
    except GristKeyNoAccessError:
        return GRIST_KEY_NO_ACCESS
    except GristKeyInsufficientAccessError as error:
        return str(error.access_level)
    except (GristUnavailableError, GristBaseUrlNotAllowedError) as error:
        log_error(
            "Vérification de l'accès de la clé API impossible : "
            f"{error.__cause__ or error}"
        )
        return GRIST_KEY_ACCESS_UNAVAILABLE
