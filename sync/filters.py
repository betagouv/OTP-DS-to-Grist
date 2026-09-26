"""Filtres de sélection des dossiers d'une synchronisation.

Ce module est le seul à connaître les variables d'environnement qui portent les
filtres : `sync.environment_config.build_environment` les écrit à partir de la
configuration de la démarche, puis elles sont relues ici pour sélectionner les
dossiers à synchroniser et pour produire l'empreinte des filtres enregistrée dans
`Sync_metadata.filters_hash` (qui détecte un changement de filtres et force une
synchronisation complète).

Les filtres sont appliqués côté client : l'API DN ne propose pas de filtrage par
groupe instructeur, et un filtrage serveur sur les dates ou les statuts rendrait
le repère `updatedSince` incohérent avec les critères retenus.
"""

import json
import os
from datetime import datetime
from typing import Any

from utils.log import log, log_error


def _read_date_filter(env_name: str) -> datetime | None:
    """Date de filtre (YYYY-MM-DD) lue dans l'environnement, ignorée si invalide."""
    value = (os.getenv(env_name) or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        log_error(f"Format de date invalide pour {env_name}: {value}")
        return None


def _read_list_filter(env_name: str) -> list[str]:
    """Liste de valeurs de filtre (séparées par des virgules) lue dans l'environnement."""
    return [value for value in (os.getenv(env_name) or "").split(",") if value.strip()]


def read_filters_from_env() -> dict[str, Any]:
    """
    Filtres de sélection des dossiers, lus dans les variables d'environnement.

    Returns:
        dict: `date_debut`, `date_fin` (datetime | None), `statuts`, `groupes`
    """
    filters = {
        "date_debut": _read_date_filter("DATE_DEPOT_DEBUT"),
        "date_fin": _read_date_filter("DATE_DEPOT_FIN"),
        "statuts": _read_list_filter("STATUTS_DOSSIERS"),
        "groupes": _read_list_filter("GROUPES_INSTRUCTEURS"),
    }

    if filters["date_debut"]:
        log(f"Filtre par date de début: {filters['date_debut']:%Y-%m-%d}")
    if filters["date_fin"]:
        log(f"Filtre par date de fin: {filters['date_fin']:%Y-%m-%d}")
    if filters["statuts"]:
        log(f"Filtre par statuts: {', '.join(filters['statuts'])}")
    if filters["groupes"]:
        log(f"Filtre par groupes instructeurs: {', '.join(filters['groupes'])}")

    return filters


def filter_dossiers(
    dossiers: list[dict[str, Any]], filters: dict[str, Any]
) -> list[dict[str, Any]]:
    """
    Applique les filtres de sélection (statut, groupe instructeur, date de dépôt)
    à une page de dossiers. Les bornes de dates sont inclusives.

    Un dossier sans date de dépôt est écarté dès qu'un filtre de date est actif.
    """
    date_debut = filters["date_debut"]
    date_fin = filters["date_fin"]
    statuts = filters["statuts"]
    groupes = filters["groupes"]

    selection: list[dict[str, Any]] = []
    for dossier in dossiers:
        if statuts and dossier["state"] not in statuts:
            continue

        if groupes and (
            not dossier.get("groupeInstructeur")
            or str(dossier["groupeInstructeur"].get("number", "")) not in groupes
        ):
            continue

        if date_debut or date_fin:
            date_depot_str = dossier.get("dateDepot")
            if not date_depot_str:
                continue
            try:
                date_depot = datetime.strptime(date_depot_str.split("T")[0], "%Y-%m-%d")
            except (ValueError, AttributeError, TypeError):
                continue
            if date_debut and date_depot < date_debut:
                continue
            if date_fin and date_depot > date_fin:
                continue

        selection.append(dossier)

    return selection


def build_filters_cache_key() -> str:
    """Construit une clé canonique JSON déterministe des filtres actifs.

    Utilisée pour détecter un changement de filtres entre deux synchronisations :
    si la clé stockée dans `Sync_metadata.filters_hash` diffère de la clé actuelle,
    une synchro complète est forcée (le delta `updatedSince` ne couvrirait sinon
    pas les dossiers nouvellement éligibles/exclus par les nouveaux filtres).

    La clé est volontairement lisible (JSON) et non un hash opaque pour faciliter
    l'inspection des filtres stockés.
    """
    # Les filtres de la synchronisation sont ceux des variables d'environnement
    # (front et scheduler les renseignent) : la clé doit refléter ces variables
    # pour détecter un changement de filtres (ex : un groupe instructeur
    # sélectionné côté front) et déclencher la synchro complète ; sinon
    # `filters_hash` resterait stable et les dossiers nouvellement
    # éligibles/exclus seraient ignorés par le delta.
    filters = {
        "date_debut": os.getenv("DATE_DEPOT_DEBUT") or None,
        "date_fin": os.getenv("DATE_DEPOT_FIN") or None,
        "statuts": _normalize_list(_split_env_list(os.getenv("STATUTS_DOSSIERS"))),
        "groupes_instructeurs": _normalize_list(
            _split_env_list(os.getenv("GROUPES_INSTRUCTEURS"))
        ),
    }

    return json.dumps(filters, sort_keys=True, ensure_ascii=False)


def _split_env_list(raw: str | None) -> list[str]:
    """Découpe une liste de valeurs legacy (séparées par des virgules) en objets propres."""
    if not raw:
        return []

    return [item.strip() for item in raw.split(",")]


def _normalize_list(value: Any) -> list[str]:
    """Normalise une liste de filtres pour garantir le déterminisme (tri, None -> [])."""
    if not value:
        return []
    try:
        return sorted(str(v) for v in value)
    except TypeError:
        return [str(value)]
