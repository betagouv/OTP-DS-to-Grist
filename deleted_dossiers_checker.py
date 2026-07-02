# -*- coding: utf-8 -*-
"""
Détection des dossiers supprimés de Démarches Simplifiées mais présents dans Grist.

Appelé après une synchro complète (force_full_sync ou première synchro).
Reçoit en entrée le set de numéros DS déjà récupérés (cache synchro) — aucun appel DS supplémentaire.
Si des filtres sont actifs (statut, date, groupe), les records Grist sont filtrés en conséquence
pour ne comparer que le même périmètre.
"""

import requests

COLUMN_ID = "dossiers_supprimes_DN"
COLUMN_LABEL = "Dossiers supprimés DN"


def _ensure_supprime_column(client, table_id, log, log_error):
    """Crée la colonne 'Dossiers supprimés DN' (Bool) si elle n'existe pas."""
    url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/columns"
    response = requests.get(url, headers=client.headers)

    if response.status_code == 200:
        existing = {col["id"] for col in response.json().get("columns", [])}
        if COLUMN_ID in existing:
            return True

    payload = {
        "columns": [
            {"id": COLUMN_ID, "fields": {"label": COLUMN_LABEL, "type": "Bool"}}
        ]
    }
    r = requests.post(url, headers=client.headers, json=payload)
    if r.status_code == 200:
        log(f"  Colonne '{COLUMN_LABEL}' créée.")
        return True

    log_error(
        f"  Impossible de créer la colonne '{COLUMN_LABEL}': {r.status_code} - {r.text}"
    )
    return False


def _get_grist_numbers_in_scope(
    client, table_id, grist_dict, api_filters, log, log_error
):
    """
    Retourne le set de numéros Grist dans le périmètre des filtres actifs.

    Si des filtres statut/date/groupe sont actifs, récupère les records complets
    pour filtrer côté Python. Sinon, utilise directement grist_dict (plus léger).
    """
    statuts = (api_filters or {}).get("statuts") or []
    date_debut_str = (api_filters or {}).get("date_debut")
    date_fin_str = (api_filters or {}).get("date_fin")
    groupes = [str(g) for g in ((api_filters or {}).get("groupes_instructeurs") or [])]

    # Aucun filtre actif → tous les records Grist sont dans le périmètre
    if not any([statuts, date_debut_str, date_fin_str, groupes]):
        return {int(k) for k in grist_dict.keys()}

    # Filtres actifs → récupérer les champs nécessaires
    url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/records"
    response = requests.get(url, headers=client.headers)

    if response.status_code != 200:
        log_error(
            f"  Erreur récupération records Grist: {response.status_code} - {response.text}"
        )
        return {int(k) for k in grist_dict.keys()}

    from datetime import datetime

    date_debut = (
        datetime.strptime(date_debut_str, "%Y-%m-%d") if date_debut_str else None
    )
    date_fin = datetime.strptime(date_fin_str, "%Y-%m-%d") if date_fin_str else None

    grist_numbers = set()
    for rec in response.json().get("records", []):
        fields = rec.get("fields", {})
        num = fields.get("dossier_number") or fields.get("number")
        if not num:
            continue

        # Filtre statut
        if statuts:
            state = fields.get("state") or fields.get("dossier_state", "")
            if state not in statuts:
                continue

        # Filtre groupe instructeur
        if groupes:
            groupe_num = str(fields.get("groupe_instructeur_number", ""))
            if groupe_num not in groupes:
                continue

        # Filtre date dépôt
        if date_debut or date_fin:
            raw = fields.get("date_depot") or fields.get("dateDepot")
            if not raw:
                continue
            try:
                date_depot = datetime.strptime(str(raw).split("T")[0], "%Y-%m-%d")
            except (ValueError, AttributeError):
                continue
            if date_debut and date_depot < date_debut:
                continue
            if date_fin and date_depot > date_fin:
                continue

        grist_numbers.add(int(num))

    log(
        f"  Dossiers Grist dans le périmètre filtré : {len(grist_numbers)}/{len(grist_dict)}"
    )
    return grist_numbers


def _mark_deleted_in_grist(client, table_id, record_ids, log, log_error):
    """PATCH en batch les records à marquer comme supprimés."""
    if not record_ids:
        return 0

    payload = {
        "records": [{"id": rid, "fields": {COLUMN_ID: True}} for rid in record_ids]
    }
    url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/records"
    response = requests.patch(url, headers=client.headers, json=payload)

    if response.status_code == 200:
        log(f"  {len(record_ids)} dossiers marqués '{COLUMN_LABEL}' dans Grist.")
        return len(record_ids)

    log_error(f"  Erreur PATCH Grist: {response.status_code} - {response.text}")
    return 0


def check_deleted_dossiers(
    client, table_id, ds_numbers_set, log, log_error, api_filters=None
):
    """
    Détecte et marque dans Grist les dossiers absents de DS après une synchro complète.

    Si api_filters est fourni, seuls les records Grist correspondant aux mêmes filtres
    sont comparés — garantissant que le périmètre DS et Grist est identique.

    Args:
        client:         Instance GristClient
        table_id:       ID de la table dossiers (ex: "Demarche_123_dossiers")
        ds_numbers_set: set[int] — numéros issus de filtered_dossiers (cache synchro)
        log:            Fonction de log du processeur principal
        log_error:      Fonction de log d'erreur
        api_filters:    dict des filtres appliqués lors de la synchro (peut être None ou {})

    Returns:
        dict: {
            "grist_in_scope": int,
            "ds_total": int,
            "newly_marked": int,
            "deleted_numbers": list[int],
        }
    """
    log("\n--- Vérification des dossiers supprimés ---")

    if not _ensure_supprime_column(client, table_id, log, log_error):
        return {}

    # Récupère {str(num): grist_row_id}
    grist_dict = client.get_existing_dossier_numbers(table_id)

    # Appliquer les filtres pour aligner le périmètre avec la synchro DS
    grist_numbers = _get_grist_numbers_in_scope(
        client, table_id, grist_dict, api_filters, log, log_error
    )

    only_in_grist = grist_numbers - ds_numbers_set

    log(f"  Dossiers DS    : {len(ds_numbers_set)}")
    log(f"  Dossiers Grist : {len(grist_numbers)}")
    log(f"  Absents de DS  : {len(only_in_grist)}")

    if only_in_grist:
        log(f"  Numéros : {sorted(only_in_grist)}")
        record_ids = [
            grist_dict[str(num)] for num in only_in_grist if str(num) in grist_dict
        ]
        newly_marked = _mark_deleted_in_grist(
            client, table_id, record_ids, log, log_error
        )
    else:
        log("  ✅ Aucun dossier supprimé détecté.")
        newly_marked = 0

    log("--- Fin vérification dossiers supprimés ---\n")

    return {
        "grist_in_scope": len(grist_numbers),
        "ds_total": len(ds_numbers_set),
        "newly_marked": newly_marked,
        "deleted_numbers": sorted(only_in_grist),
    }
