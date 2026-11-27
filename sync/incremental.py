"""Synchronisation incrémentale.

Décide si une synchronisation demande à DN tous les dossiers (synchronisation
complète) ou seulement ceux modifiés (`updatedSince` de l'API DN) et supprimés
depuis une date, et calcule ces dates pour la synchronisation suivante.

Le processus parent prend la décision, d'après la dernière synchronisation
enregistrée dans `sync_logs`, et transmet les dates au sous-processus par son
environnement : ce module est le seul à connaître ces variables.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import SyncLog

# Format des dates transmises à l'API DN
ISO_DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# Variables d'environnement qui transmettent les dates au sous-processus
MODIFIED_DOSSIERS_SINCE_ENV = "MODIFIED_DOSSIERS_SINCE"
DELETED_DOSSIERS_SINCE_ENV = "DELETED_DOSSIERS_SINCE"


@dataclass(frozen=True)
class SinceDates:
    """Dates depuis lesquelles une synchronisation demande à DN les dossiers
    modifiés et supprimés ; None si elle les demande tous."""

    modified_dossiers_since: str | None = None
    deleted_dossiers_since: str | None = None


def last_sync_with_dates(db: Session, otp_config_id: int) -> SyncLog | None:
    """
    Dernière synchronisation de la configuration qui a laissé des dates à la
    suivante ; None s'il n'y en a pas.

    Une synchronisation dont le sous-processus a échoué n'en laisse pas : elle
    est ignorée, et la suivante repart des mêmes dates que celle en échec.
    """
    return db.scalars(
        select(SyncLog)
        .where(
            SyncLog.otp_config_id == otp_config_id,
            SyncLog.modified_dossiers_since.is_not(None),
        )
        .order_by(SyncLog.timestamp.desc(), SyncLog.id.desc())
        .limit(1)
    ).first()


def needs_full_sync(
    previous: SyncLog | None,
    demarche_number: str,
    filters_key: str,
    forced: bool = False,
) -> bool:
    """
    Vrai si la synchronisation en cours doit demander tous les dossiers à DN,
    d'après la dernière synchronisation qui a laissé des dates (`previous`,
    None s'il n'y en a pas), la démarche de la configuration et l'empreinte des
    filtres actuels.

    C'est le cas si l'utilisateur l'a demandé (`forced`), s'il n'y a pas de
    synchronisation précédente, si la démarche
    de la configuration a changé depuis, ou si les filtres ont changé : le
    delta `updatedSince` ne verrait alors que les dossiers modifiés et
    ignorerait ceux nouvellement éligibles/exclus par les nouveaux critères.
    """
    return (
        forced
        or previous is None
        or str(previous.demarche_number) != str(demarche_number)
        or previous.filters_hash != filters_key
    )


def dates_to_request(previous: SyncLog | None, full_sync: bool) -> SinceDates:
    """
    Dates depuis lesquelles la synchronisation en cours demande à DN les
    dossiers modifiés et supprimés : celles enregistrées par la précédente,
    aucune en synchronisation complète.
    """
    if full_sync or previous is None:
        return SinceDates()

    return SinceDates(
        modified_dossiers_since=_to_iso(previous.modified_dossiers_since),
        deleted_dossiers_since=_to_iso(previous.deleted_dossiers_since),
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


def dates_to_env(dates: SinceDates) -> dict[str, str]:
    """Variables d'environnement qui transmettent les dates au sous-processus
    (vides si aucune date)."""
    return {
        MODIFIED_DOSSIERS_SINCE_ENV: dates.modified_dossiers_since or "",
        DELETED_DOSSIERS_SINCE_ENV: dates.deleted_dossiers_since or "",
    }


def dates_from_env(env: Mapping[str, str] = os.environ) -> SinceDates:
    """Dates transmises par le processus parent (voir `dates_to_env`)."""
    return SinceDates(
        modified_dossiers_since=env.get(MODIFIED_DOSSIERS_SINCE_ENV) or None,
        deleted_dossiers_since=env.get(DELETED_DOSSIERS_SINCE_ENV) or None,
    )


# --- Helpers privés (module) ---
def _to_iso(value: datetime | None) -> str | None:
    """Date enregistrée en base, au format transmis à DN."""
    if value is None:
        return None

    return value.astimezone(timezone.utc).strftime(ISO_DATE_FORMAT)
