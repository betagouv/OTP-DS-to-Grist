from datetime import datetime, timezone
from typing import Any

from utils.log import log_error

# Format attendu par une colonne DateTime de Grist : ISO 8601 en UTC, à la seconde.
FORMAT_GRIST_DATETIME = "%Y-%m-%dT%H:%M:%SZ"


def format_value(
    value: Any,
    value_type: str,
    *,
    dossier_number: int,
    champ_label: str,
) -> Any:
    """
    Convertit une valeur DS vers le type de colonne Grist attendu.

    Deux contrats encadrent les dates :

    - en entrée, DS renvoie de l'ISO 8601, sous deux types déclarés par son
      schéma GraphQL : `ISO8601DateTime` (dates de dossier, champs datetime) et
      `ISO8601Date` (champs date) ;
    - en sortie, une colonne DateTime de Grist attend une date en UTC ; Grist la
      stocke en secondes depuis epoch, le fuseau de la colonne ne servant qu'à
      l'affichage. La forme canonique `…Z` est donc produite, ce qui rend les
      valeurs comparables et supprime toute ambiguïté de fuseau.

    `dossier_number` et `champ_label` sont obligatoires : une valeur abandonnée ou
    transmise telle quelle est un échec silencieux, seulement visible en Grist ou
    dans la cellule concernée. Les nommer au moment de l'appel évite d'avoir à
    retrouver le dossier après coup.

    Args:
        value: Valeur extraite de la démarche.
        value_type: Type de colonne Grist ('Text', 'Int', 'Numeric', 'Bool', 'DateTime').
        dossier_number: Numéro du dossier source, pour le log.
        champ_label: Libellé de la colonne, pour le log.

    Returns:
        La valeur convertie, ou None si elle n'est pas convertible.
    """
    if value is None:
        return None

    if value_type == "DateTime":
        if isinstance(value, str):
            if value:
                try:
                    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    dt = None
                if dt is not None:
                    if dt.tzinfo is not None:
                        dt = dt.astimezone(timezone.utc)
                    return dt.strftime(FORMAT_GRIST_DATETIME)
            log_error(
                f"Date illisible pour le dossier {dossier_number}, champ "
                f"{champ_label} : {str(value)[:80]!r} (transmise telle quelle)"
            )

            return value

        return value

    if value_type == "Text":
        return str(value)

    if value_type in ["Int", "Numeric"]:
        try:
            if value_type == "Int":
                return int(float(value)) if value else None
            return float(value) if value else None
        except (ValueError, TypeError):
            log_error(
                f"Valeur non convertible en {value_type} pour le dossier "
                f"{dossier_number}, champ {champ_label} : {str(value)[:80]!r} "
                "(écrite vide)"
            )
            return None

    if value_type == "Bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ["true", "1", "yes", "oui", "vrai"]
        return bool(value)

    return value
