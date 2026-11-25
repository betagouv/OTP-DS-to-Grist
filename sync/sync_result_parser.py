import json
from datetime import datetime, timezone

from utils.log import MAX_SYNC_ERRORS, log

SYNC_METADATA_PREFIX = "SYNC_METADATA: "
SYNC_ERRORS_PREFIX = "SYNC_ERRORS: "


def emit_sync_metadata(
    duration_seconds: float, force_full_sync: bool, filters_hash: str
) -> None:
    """Émet les métadonnées de fin de sync : durée, force_full_sync, filters_hash.

    Ces valeurs alimentent sync_logs ; la ligne technique n'est pas destinée
    à l'utilisateur.
    """
    log(
        SYNC_METADATA_PREFIX
        + json.dumps(
            {
                "duration_seconds": duration_seconds,
                "force_full_sync": force_full_sync,
                "filters_hash": filters_hash,
            },
            sort_keys=True,
        ),
        0,
    )


def timestamped_error(message: str) -> dict[str, str]:
    """Erreur horodatée à l'instant présent (UTC, à la milliseconde)."""
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return {"timestamp": timestamp, "message": message}


def emit_sync_errors(
    dossier_errors: dict[str, dict[str, str]], general_errors: list[dict[str, str]]
) -> None:
    """Émet les erreurs de fin de sync, s'il y en a : première erreur de chaque
    dossier en échec (au plus MAX_SYNC_ERRORS, dans l'ordre des échecs, avec
    leur nombre total) et erreurs générales, sans lien avec un dossier.

    Ligne technique, non destinée à l'utilisateur.
    """
    if not dossier_errors and not general_errors:
        return

    first_dossier_errors = list(dossier_errors.items())[:MAX_SYNC_ERRORS]
    log(
        SYNC_ERRORS_PREFIX
        + json.dumps(
            {
                "dossiers": [
                    {"dossier": number, **error}
                    for number, error in first_dossier_errors
                ],
                "dossiers_total": len(dossier_errors),
                "general": general_errors,
            },
            ensure_ascii=False,
        ),
        0,
    )


def read_sync_errors(output_lines: list[str]) -> dict:
    """Erreurs émises par le sous-processus (ligne SYNC_ERRORS) : aucune si la
    ligne est absente ; si elle est illisible, une erreur générale le signale."""
    errors = {"dossiers": [], "dossiers_total": 0, "general": []}
    for line in output_lines:
        if not line.startswith(SYNC_ERRORS_PREFIX):
            continue
        payload = line[len(SYNC_ERRORS_PREFIX) :]
        try:
            emitted = json.loads(payload)
        except ValueError:
            emitted = None
        if not isinstance(emitted, dict):
            errors["general"].append(
                timestamped_error(f"Ligne SYNC_ERRORS illisible : {payload}")
            )
            continue
        errors.update(emitted)
    return errors


def _parse_success_count(line: str) -> tuple[int | None, int | None]:
    """Extrait le nombre de succès depuis une ligne de log"""
    if "Dossiers traités avec succès:" not in line:
        return None, None

    try:
        parts = line.split(":", 1)
        if len(parts) <= 1:
            return None, None

        num_str = parts[1].strip()

        if "/" in num_str:
            # Format "X/Y"
            success = int(num_str.split("/")[0].strip())
            total = int(num_str.split("/")[1].strip())
            return success, total

        # Format "X"
        success = int(num_str)
        return success, None
    except (ValueError, IndexError):
        return None, None


def _parse_error_count(line: str) -> int | None:
    """Extrait le nombre d'erreurs depuis une ligne de log"""
    if "Dossiers en échec:" not in line:
        return None

    try:
        parts = line.split(":", 1)
        if len(parts) <= 1:
            return None
        return int(parts[1].strip())
    except (ValueError, IndexError):
        return None


class SyncMetadataParseError(Exception):
    """Métadonnées de fin de sync présentes dans la sortie mais illisibles."""


def _parse_sync_metadata(line: str) -> dict | None:
    """Extrait les métadonnées de fin de sync d'une ligne de sortie.

    Renvoie None si la ligne n'en porte pas ; lève SyncMetadataParseError
    si elles sont présentes mais illisibles.
    """
    if not line.startswith(SYNC_METADATA_PREFIX):
        return None
    payload = line[len(SYNC_METADATA_PREFIX) :]
    try:
        metadata = json.loads(payload)
    except ValueError as e:
        raise SyncMetadataParseError(f"JSON illisible: {payload!r}") from e
    if not isinstance(metadata, dict):
        raise SyncMetadataParseError(f"Contenu non-dict: {payload!r}")
    return metadata


def parse_output(output_lines: list[str]) -> dict:
    """
    Parse les lignes de log et retourne les statistiques de synchronisation.
    Args:
        output_lines: Liste des lignes de sortie du script de synchronisation
    Returns:
        dict avec: success, sync_reason, message, dossier_count,
                   success_count, error_count, total_processed,
                   errors, timestamp, already_up_to_date
    """
    success_count = 0
    error_count = 0
    total_processed = 0
    errors_list = []

    nb_deleted = 0
    duration_seconds = None
    force_full_sync = None
    filters_hash = None
    sync_metadata_error = False
    # La ligne SYNC_ERRORS porte des messages libres : une phrase de bilan
    # qu'ils contiendraient ne doit pas fausser les statistiques
    output_lines = [
        line for line in output_lines if not line.startswith(SYNC_ERRORS_PREFIX)
    ]
    # Parser la sortie pour extraire les statistiques
    for line in output_lines:
        # Essayer de parser succès
        success_parsed, total_parsed = _parse_success_count(line)
        if success_parsed is not None:
            success_count = success_parsed
            if total_parsed is not None:
                total_processed = total_parsed

        # Essayer de parser erreurs
        error_parsed = _parse_error_count(line)
        if error_parsed is not None:
            error_count = error_parsed

        # Essayer de parser total (si présent dans logs)
        if "Total dossiers traités:" in line:
            try:
                total_processed = int(line.split(":")[1].strip())
            except (ValueError, IndexError):
                pass

        # Métadonnées de fin de sync : si présentes mais illisibles, le flag
        # sync_metadata_error le signale (compteurs préservés).
        try:
            sync_metadata = _parse_sync_metadata(line)
        except SyncMetadataParseError:
            sync_metadata_error = True
        else:
            if sync_metadata is not None:
                duration_seconds = sync_metadata.get("duration_seconds")
                force_full_sync = sync_metadata.get("force_full_sync")
                filters_hash = sync_metadata.get("filters_hash")

        # Essayer de parser le nombre de dossiers supprimés côté DN
        if "Nombre de dossiers marqués supprimés dans Grist :" in line:
            try:
                nb_deleted = int(
                    line.split("Nombre de dossiers marqués supprimés dans Grist :")[
                        -1
                    ].strip()
                )
            except (ValueError, IndexError):
                pass

    # Calculer total si pas déjà extrait
    if total_processed == 0:
        total_processed = success_count + error_count

    # Détecter si Grist était déjà à jour
    already_up_to_date = (
        success_count == 0
        and error_count == 0
        and any(
            "déjà à jour" in line or "Aucun dossier modifié" in line
            for line in output_lines
        )
    )

    message = (
        f"Synchronisation terminée: {success_count}/{total_processed} dossiers synchronisés"
        if error_count == 0
        else f"Synchronisation terminée avec {error_count} erreurs sur {total_processed} dossiers"
    )
    if nb_deleted > 0:
        message += f" — {nb_deleted} dossier(s) supprimé(s) dans DN (mis à jour dans Grist)"

    return {
        "success": error_count == 0,
        "sync_reason": "already_up_to_date" if already_up_to_date else "synced",
        "message": message,
        "dossier_count": total_processed,
        "success_count": success_count,
        "error_count": error_count,
        "total_processed": total_processed,
        "deleted_dossiers_count": nb_deleted,
        "duration_seconds": duration_seconds,
        "force_full_sync": force_full_sync,
        "filters_hash": filters_hash,
        "sync_metadata_error": sync_metadata_error,
        "errors": errors_list,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
