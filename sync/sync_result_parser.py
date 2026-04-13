from datetime import datetime, timezone


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

    return {
        "success": error_count == 0,
        "sync_reason": "already_up_to_date" if already_up_to_date else "synced",
        "message": f"Synchronisation terminée: {success_count}/{total_processed} dossiers synchronisés"
        if error_count == 0
        else f"Synchronisation terminée avec {error_count} erreurs sur {total_processed} dossiers",
        "dossier_count": total_processed,
        "success_count": success_count,
        "error_count": error_count,
        "total_processed": total_processed,
        "errors": errors_list,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
