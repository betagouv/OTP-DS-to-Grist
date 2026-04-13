import re
import subprocess


def extract_error_parts(e: Exception, output_lines: list[str]) -> list[str]:
    """Extrait les messages d'erreur depuis stderr et stdout.

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
        stderr_errors = [
            line.strip()
            for line in e.stderr.strip().split("\n")
            if line.strip()
        ]
        error_parts.extend(stderr_errors)

    # log_error() écrit dans stdout avec le préfixe "ERREUR: "
    # On extrait ces lignes du stdout capturé
    # regex: ^ERREUR:\s* matches "ERREUR:" suivi de 0+ espaces pour différends formats
    stdout_errors = [
        re.sub(r'^ERREUR:\s*', '', line, flags=re.IGNORECASE)
        for line in output_lines
        if re.search(r'ERREUR:', line, re.IGNORECASE)
    ]
    error_parts.extend(stdout_errors)

    return error_parts
