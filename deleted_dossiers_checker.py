# -*- coding: utf-8 -*-
"""
Détection des dossiers supprimés de Démarches Simplifiées, via le champ
`deletedDossiers` de l'API DN. Interroge l'API directement (plus de comparaison
par absence) et met à jour les colonnes dossiers_supprimes_DN, date_suppression
et raison_suppression dans Grist.
"""

import requests

from queries_graphql import get_deleted_dossiers

COLUMN_ID = "dossiers_supprimes_DN"
COLUMN_LABEL = "Dossiers supprimés DN"
DATE_COLUMN_ID = "date_suppression"
REASON_COLUMN_ID = "raison_suppression"


def _ensure_deletion_columns(client, table_id, log, log_error):
    """Crée les colonnes de suppression (Bool/DateTime/Text) si elles n'existent pas."""
    url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/columns"
    response = requests.get(url, headers=client.headers)
    existing = (
        {col["id"] for col in response.json().get("columns", [])}
        if response.status_code == 200
        else set()
    )

    needed = [
        {"id": COLUMN_ID, "fields": {"label": COLUMN_LABEL, "type": "Bool"}},
        {
            "id": DATE_COLUMN_ID,
            "fields": {"label": "Date de suppression", "type": "DateTime"},
        },
        {
            "id": REASON_COLUMN_ID,
            "fields": {"label": "Raison de suppression", "type": "Text"},
        },
    ]
    missing = [c for c in needed if c["id"] not in existing]
    if not missing:
        return True

    r = requests.post(url, headers=client.headers, json={"columns": missing})
    if r.status_code == 200:
        log(f"  Colonnes créées : {[c['id'] for c in missing]}")
        return True

    log_error(f"  Impossible de créer les colonnes : {r.status_code} - {r.text}")
    return False


def _mark_deleted_in_grist(
    client, table_id, grist_dict, deleted_dossiers, log, log_error
):
    """PATCH en batch les records à marquer comme supprimés, avec date et raison."""
    records = []
    for d in deleted_dossiers:
        num_str = str(d["number"])
        if num_str not in grist_dict:
            continue
        records.append(
            {
                "id": grist_dict[num_str],
                "fields": {
                    COLUMN_ID: True,
                    DATE_COLUMN_ID: d.get("dateSupression"),
                    REASON_COLUMN_ID: d.get("reason"),
                },
            }
        )

    if not records:
        return 0

    url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/records"
    response = requests.patch(url, headers=client.headers, json={"records": records})

    if response.status_code == 200:
        log(f"  {len(records)} dossiers marqués '{COLUMN_LABEL}' dans Grist.")
        return len(records)

    log_error(f"  Erreur PATCH Grist: {response.status_code} - {response.text}")
    return 0


def check_deleted_dossiers(
    client, table_id, demarche_number, log, log_error, deleted_since=None
):
    """
    Récupère les dossiers supprimés directement depuis l'API DN (deletedDossiers)
    et met à jour les colonnes correspondantes dans Grist.

    Args:
        client:          Instance GristClient
        table_id:        ID de la table dossiers
        demarche_number: Numéro de la démarche
        log:             Fonction de log du processeur principal
        log_error:       Fonction de log d'erreur
        deleted_since:   ISO8601DateTime optionnel, pour limiter aux suppressions récentes

    Returns:
        dict: {"ds_deleted_total": int, "newly_marked": int, "deleted_numbers": list[int]}
    """
    log("\n--- Vérification des dossiers supprimés (API DN) ---")
    log(
        f"  deleted_since utilisé : {deleted_since or '(aucun — récupération complète)'}"
    )

    if not _ensure_deletion_columns(client, table_id, log, log_error):
        return {}

    deleted_dossiers = get_deleted_dossiers(
        demarche_number, deleted_since=deleted_since
    )
    log(f"  Dossiers supprimés côté DN : {len(deleted_dossiers)}")

    if not deleted_dossiers:
        log("  ✅ Aucun dossier supprimé détecté.")
        log("--- Fin vérification dossiers supprimés ---\n")
        return {"ds_deleted_total": 0, "newly_marked": 0}

    grist_dict = client.get_existing_dossier_numbers(table_id)
    newly_marked = _mark_deleted_in_grist(
        client, table_id, grist_dict, deleted_dossiers, log, log_error
    )

    log("--- Fin vérification dossiers supprimés ---\n")

    return {
        "ds_deleted_total": len(deleted_dossiers),
        "newly_marked": newly_marked,
        "deleted_numbers": sorted(d["number"] for d in deleted_dossiers),
    }
