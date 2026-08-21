"""
Formatage de labels en IDs de colonnes Grist valides.
"""
import hashlib
import re
import unicodedata


def label_to_column_id(name: str, max_length: int = 150) -> str:
    """
    Transforme un label libre en ID de colonne Grist valide.

    Supprime les accents, remplace les caractères spéciaux par des underscores,
    et tronque avec un hash si nécessaire pour garantir l'unicité.

    Args:
        name: Le nom original de la colonne
        max_length: Longueur maximale autorisée (défaut: 150)

    Returns:
        str: ID de colonne normalisé pour Grist
    """
    if not name:
        return "column"

    name = name.strip()
    name = re.sub(r"\s+", " ", name)

    name = name.replace("'", "_")
    name = name.replace("\u2019", "_")  # Apostrophe typographique
    name = name.replace("`", "_")  # Accent grave utilisé comme apostrophe

    # Supprimer les accents
    name = unicodedata.normalize("NFKD", name)
    name = "".join([c for c in name if not unicodedata.combining(c)])

    # Convertir en minuscules et remplacer les caractères non alphanumériques
    name = name.lower()
    name = re.sub(r"[^a-z0-9_]", "_", name)

    # Éliminer les underscores multiples consécutifs
    name = re.sub(r"_+", "_", name)

    # Éliminer les underscores en début et fin
    name = name.strip("_")

    # S'assurer que le nom commence par une lettre
    if not name or not name[0].isalpha():
        name = "col_" + (name or "")

    # Tronquer si nécessaire avec hash pour unicité
    if len(name) > max_length:
        hash_part = hashlib.md5(name.encode()).hexdigest()[:6]
        name = f"{name[:max_length - 7]}_{hash_part}"

    return name


def ds_label_to_column_id(name: str, max_length: int = 150) -> str:
    """
    Transforme un label DS numéroté en ID de colonne Grist valide.

    Supprime les numéros en début de chaîne (ex: "1. Nom", "2) Prénom")
    avant d'appliquer la normalisation standard.

    À utiliser pour tout label provenant de l'API Démarches Simplifiées.

    Args:
        name: Le nom original du champ DS
        max_length: Longueur maximale autorisée (défaut: 150)

    Returns:
        str: ID de colonne normalisé pour Grist
    """
    # Supprimer les numéros en début type "1. ", "2. ", "3) ", etc.
    if name:
        name = re.sub(r"^[\d]+[\.\)]\s*", "", name)
    return label_to_column_id(name, max_length)
