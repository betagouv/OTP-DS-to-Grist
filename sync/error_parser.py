import re
import subprocess


def extract_error_parts(e: Exception, output_lines: list[str]) -> list[str]:
    """Extrait les messages d'erreur depuis stderr et stdout.

    Les artefacts de traceback Python du stderr (en-tête, frames indentées)
    sont filtrés : seul le message d'erreur final reste affichable, le détail
    complet étant conservé dans les logs.

    Args:
        e: Exception levée (peut être CalledProcessError)
        output_lines: Lignes stdout capturées

    Returns:
        Liste des messages d'erreur individuels
    """
    error_parts = []

    # CalledProcessError contient le stderr du subprocess
    # e.stderr est une chaîne potentiellement multi-lignes
    # On la divise en lignes individuelles et on filtre les vides
    if isinstance(e, subprocess.CalledProcessError) and e.stderr:
        error_parts.extend(stderr_error_messages(e.stderr))

    # log_error() écrit dans stdout avec le préfixe "ERREUR: "
    error_parts.extend(
        message
        for line in output_lines
        if (message := error_message(line)) is not None
    )

    return error_parts


def error_message(line: str) -> str | None:
    """Message porté par une ligne `ERREUR: …` de la sortie du script (préfixe
    retiré, casse ignorée) ; None pour toute autre ligne."""
    if not re.search(r"ERREUR:", line, re.IGNORECASE):
        return None

    return re.sub(r"^ERREUR:\s*", "", line, flags=re.IGNORECASE)


def stderr_error_messages(stderr: str) -> list[str]:
    """Lignes affichables du stderr du script : lignes vides et artefacts de
    traceback Python écartés, seul le message d'exception final reste."""
    return [
        line.strip()
        for line in stderr.strip().split("\n")
        if line.strip() and not _is_traceback_artifact(line)
    ]


# --- Helpers privés ---


def _is_traceback_artifact(line: str) -> bool:
    """Une ligne brute de stderr appartenant à un bloc de traceback Python.

    L'en-tête et les frames sont indentés ; le message d'exception final d'un
    traceback ne l'est pas : il reste donc affichable.
    """
    if line.startswith("Traceback (most recent call last):"):
        return True

    return line.startswith((" ", "\t", 'File "'))
