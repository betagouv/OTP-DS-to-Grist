import base64


def decode_base64_id(base64_id: str) -> str:
    """
    Décode un ID en Base64 utilisé par l'API GraphQL.

    Args:
        base64_id: ID en format Base64

    Returns:
        ID décodé
    """
    try:
        # Décodage Base64
        decoded = base64.b64decode(base64_id).decode("utf-8")

        # Les IDs GraphQL sont souvent de la forme "TypeName:id"
        if ":" in decoded:
            return decoded.split(":")[-1]

        # Extrait juste le nombre si le format est "Champ-123456"
        if "-" in decoded:
            return decoded.split("-")[-1]

        return decoded
    except Exception:
        # Si le décodage échoue, retourne l'ID original
        return base64_id