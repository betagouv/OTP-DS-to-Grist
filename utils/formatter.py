import json
from typing import Any


def unwrap_json_list(raw: str) -> str:
    """
    Convertit '["a", "b"]' en 'a, b', laisse les strings normales intactes.
    Nécessaire car les anciennes démarches DS retournent les valeurs de listes
    déroulantes comme chaînes simples, tandis que les nouvelles les retournent
    sous forme de chaînes JSON encodées.
    """
    if not isinstance(raw, str) or not raw.startswith("["):
        return raw

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw

    if isinstance(parsed, list):
        return ", ".join(str(v) for v in parsed)

    return raw


def build_filters_key(api_filters: dict[str, Any] | None) -> str:
    """Construit une clé canonique JSON déterministe des filtres actifs.

    Utilisée pour détecter un changement de filtres entre deux synchronisations :
    si la clé stockée dans `Sync_metadata.filters_hash` diffère de la clé actuelle,
    une synchro complète est forcée (le delta `updatedSince` ne couvrirait sinon
    pas les dossiers nouvellement éligibles/exclus par les nouveaux filtres).

    La clé est volontairement lisible (JSON) et non un hash opaque pour faciliter
    l'inspection des filtres stockés.

    NB : la clé est non-versionnée ET ne couvre que `api_filters` (chemin optimisé).
    L'ajout futur d'un champ de filtre dans cette fonction modifiera donc la clé et
    déclenchera une synchro complète ponctuelle pour tous les utilisateurs existants
    (comportement attendu et sûr). Le chemin legacy (variables d'environnement
    DATE_DEPOT_DEBUT / STATUTS_DOSSIERS / ...) n'est PAS couvert par cette clé :
    à vérifier/nettoyer si ce chemin se révèle être du code mort.
    """
    filters = {
        "date_debut": (api_filters or {}).get("date_debut"),
        "date_fin": (api_filters or {}).get("date_fin"),
        "statuts": _normalize_list((api_filters or {}).get("statuts")),
        "groupes_instructeurs": _normalize_list(
            (api_filters or {}).get("groupes_instructeurs")
        ),
    }
    return json.dumps(filters, sort_keys=True, ensure_ascii=False)


def _normalize_list(value: Any) -> list[str]:
    """Normalise une liste de filtres pour garantir le déterminisme (tri, None -> [])."""
    if not value:
        return []
    try:
        return sorted(str(v) for v in value)
    except TypeError:
        return [str(value)]
