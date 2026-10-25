"""
Utilitaires transverses propres à Grist.

Regroupe les règles imposées par Grist que plusieurs modules doivent appliquer
de manière identique, comme la construction des identifiants de colonnes et de
tables à partir des libellés Démarche Numérique.
"""

import hashlib
import re
import unicodedata


def normalize_column_name(name: str | None, max_length: int = 150) -> str:
    """
    Normalise un libellé en identifiant valide pour Grist (colonne ou table).

    Le schéma, l'extraction des dossiers et l'écriture des blocs répétables
    doivent produire le même identifiant pour un même libellé : sinon les
    valeurs ne trouvent pas leur colonne et sont ignorées.
    """
    # Supprimer les espaces en début et fin, et remplacer les espaces consécutifs par un seul espace
    name = (name or "").strip()
    name = re.sub(r"\s+", " ", name)

    name = name.replace("'", "_")
    name = name.replace("`", "_")  # Accent grave utilisé comme apostrophe

    # Supprimer les numéros de début type "1. ", "2) ", etc.
    name = re.sub(r"^[\d]+[\.\)]\s*", "", name)

    # Supprimer les accents
    name = unicodedata.normalize("NFKD", name)
    name = "".join([c for c in name if not unicodedata.combining(c)])

    # Convertir en minuscules et remplacer les caractères non alphanumériques par des underscores
    name = name.lower()
    name = re.sub(r"[^a-z0-9_]", "_", name)

    # Éliminer les underscores multiples consécutifs
    name = re.sub(r"_+", "_", name)

    # Éliminer les underscores en début et fin
    name = name.strip("_")

    # Libellé vide ou sans aucun caractère exploitable
    if not name:
        return "column"

    # S'assurer que le nom commence par une lettre
    if not name[0].isalpha():
        name = "col_" + name

    # Tronquer si nécessaire à max_length caractères
    if len(name) > max_length:
        # Générer un hash pour garantir l'unicité
        hash_part = hashlib.md5(name.encode()).hexdigest()[:6]
        name = f"{name[: max_length - 7]}_{hash_part}"

    return name
