def parse_success_count(line):
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
        else:
            # Format "X"
            success = int(num_str)
            return success, None
    except (ValueError, IndexError):
        return None, None

def parse_error_count(line):
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

