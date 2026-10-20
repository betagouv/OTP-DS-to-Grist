import json
from datetime import datetime, timezone

from utils.log import log

SYNC_METADATA_PREFIX = "SYNC_METADATA: "


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

    # Détecter si Grist était déjà à jour. La ligne de rafraîchissement des
    # labels contient « déjà à jour » sans rien dire de l'état des dossiers :
    # elle est exclue pour ne pas classer à tort un sync à 0 dossier.
    already_up_to_date = (
        success_count == 0
        and error_count == 0
        and any(
            ("déjà à jour" in line or "Aucun dossier modifié" in line)
            and "labels" not in line.lower()
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
