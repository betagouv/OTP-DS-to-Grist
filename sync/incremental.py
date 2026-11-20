"""Synchronisation incrémentale.

Décide si une synchronisation demande à DN tous les dossiers (synchronisation
complète) ou seulement ceux modifiés (`updatedSince` de l'API DN) et supprimés
depuis une date, et calcule ces dates pour la synchronisation suivante.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from utils.log import log

# Format des dates transmises à l'API DN
ISO_DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@dataclass(frozen=True)
class SinceDates:
    """Dates depuis lesquelles une synchronisation demande à DN les dossiers
    modifiés et supprimés ; None si elle les demande tous."""

    modified_dossiers_since: str | None = None
    deleted_dossiers_since: str | None = None


def needs_full_sync(previous: dict[str, Any] | None, filters_key: str) -> bool:
    """
    Vrai si la synchronisation en cours doit demander tous les dossiers à DN,
    d'après l'état laissé par la précédente (`previous`, None s'il n'y en a
    pas) et l'empreinte des filtres actuels.

    C'est le cas s'il n'y a pas d'état précédent (première synchro ou table
    Sync_metadata supprimée), si une synchro complète a été demandée, ou si les
    filtres ont changé : le delta `updatedSince` ne verrait alors que les
    dossiers modifiés et ignorerait ceux nouvellement éligibles/exclus par les
    nouveaux critères.
    """
    if previous is None:
        return True

    full_sync = bool(previous.get("force_full_sync", False))
    # `filters_hash` est `None` la première fois (créé par le déploiement
    # précédent) → synchro complète ponctuelle, puis retour au delta normal.
    if previous.get("filters_hash") != filters_key:
        log(
            "Changement de filtres détecté (filters_hash différent) → sync complète forcée"
        )
        full_sync = True

    return full_sync


def dates_to_request(previous: dict[str, Any] | None, full_sync: bool) -> SinceDates:
    """
    Dates depuis lesquelles la synchronisation en cours demande à DN les
    dossiers modifiés et supprimés : celles enregistrées par la précédente,
    aucune en synchronisation complète.
    """
    if full_sync or previous is None:
        return SinceDates()

    return SinceDates(
        modified_dossiers_since=_grist_date_to_iso(
            previous.get("updated_since_cursor")
        ),
        deleted_dossiers_since=previous.get("deleted_since_cursor"),
    )


def next_dates_to_request(
    current: SinceDates,
    sync_start_time: str,
    dossiers_complete: bool,
    deletions_checked: bool,
) -> SinceDates:
    """
    Dates à enregistrer en fin de synchronisation : la synchronisation suivante
    demandera à DN les dossiers modifiés et supprimés depuis ces dates.

    Elles avancent à l'heure de début de la synchronisation en cours, sauf si
    elle n'a pas traité tous les dossiers (`dossiers_complete` faux : page DN
    perdue ou dossier en échec) : le delta ne redemande à DN que les dossiers
    modifiés après la date, l'avancer perdrait ceux non traités. La date des
    suppressions reste aussi en place si leur vérification n'a pas abouti.
    """
    modified_dossiers_since = (
        sync_start_time if dossiers_complete else current.modified_dossiers_since
    )
    deleted_dossiers_since = (
        sync_start_time
        if dossiers_complete and deletions_checked
        else current.deleted_dossiers_since
    )

    return SinceDates(
        modified_dossiers_since=modified_dossiers_since,
        deleted_dossiers_since=deleted_dossiers_since,
    )


# --- Helpers privés (module) ---
def _grist_date_to_iso(value: Any) -> Any:
    """Convertit un horodatage numérique (colonne Grist de type DateTime, #284)
    en date transmise à DN ; toute autre valeur est rendue telle quelle."""
    if value and isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).strftime(ISO_DATE_FORMAT)

    return value
