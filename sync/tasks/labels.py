# -*- coding: utf-8 -*-
"""
Rafraîchissement des labels (étiquettes) des dossiers dans Grist.
Ce script interroge tous les dossiers de la démarche avec une requête minimaliste
(number + labels) et met à jour les seules lignes dont les labels ont changé.
"""

import time

from dn.client import get_demarche_dossiers_labels_only
from dn.extract import build_label_fields

BATCH_SIZE = 500


def sync_labels_for_demarche(
    client, table_id, demarche_number, log=print, log_error=print
):
    """
    Rafraîchit les colonnes label_names / labels_json des dossiers présents dans Grist.

    Args:
        client:          Instance GristClient
        table_id:        ID de la table dossiers
        demarche_number: Numéro de la démarche
        log:             Fonction de log du processeur principal
        log_error:       Fonction de log d'erreur

    Returns:
        dict: {"checked": int, "updated": int, "missing_in_grist": int}
    """
    start_time = time.time()
    result = {"checked": 0, "updated": 0, "missing_in_grist": 0}
    log("\n--- Rafraîchissement des labels ---")

    existing = _fetch_existing_labels(client, table_id)
    if not existing:
        log("  Aucun dossier dans Grist — rien à rafraîchir.")
        log("--- Fin rafraîchissement des labels ---\n")
        return result

    dossiers = get_demarche_dossiers_labels_only(demarche_number)
    log(f"  {len(dossiers)} dossier(s) interrogé(s) côté DN")

    to_update = []
    missing_in_grist = 0

    for dossier in dossiers:
        num_str = str(dossier.get("number"))
        current = existing.get(num_str)
        if not current:
            missing_in_grist += 1
            continue

        fields = build_label_fields(dossier.get("labels"))
        if (
            fields["label_names"] == current["label_names"]
            and fields["labels_json"] == current["labels_json"]
        ):
            continue

        to_update.append({"id": current["grist_id"], "fields": fields})

    if not to_update:
        log("  Labels déjà à jour (aucun changement)")

    updated = _patch_records(client, table_id, to_update, log, log_error)

    log(f"[TIMING] Labels rafraîchis en {time.time() - start_time:.1f}s")
    log("--- Fin rafraîchissement des labels ---\n")

    result.update(
        {
            "checked": len(dossiers),
            "updated": updated,
            "missing_in_grist": missing_in_grist,
        }
    )

    return result


# --- Helpers privés (module) ---


def _fetch_existing_labels(client, table_id):
    """
    Récupère l'état actuel des labels dans Grist.

    Returns:
        dict: {str(dossier_number): {"grist_id": int, "label_names": str, "labels_json": str}}
    """
    response = client.get_records(table_id)

    if response.status_code != 200:
        raise RuntimeError(
            f"Lecture de la table {table_id} impossible : "
            f"{response.status_code} - {response.text}"
        )

    existing = {}
    for record in response.json().get("records", []):
        fields = record.get("fields", {})
        dossier_num = fields.get("dossier_number") or fields.get("number")
        if not dossier_num:
            continue
        existing[str(dossier_num)] = {
            "grist_id": record.get("id"),
            "label_names": fields.get("label_names") or "",
            "labels_json": fields.get("labels_json") or "",
        }

    return existing


def _patch_records(client, table_id, records, log, log_error):
    """PATCH les enregistrements par lots. Retourne le nombre de lignes mises à jour."""
    updated = 0

    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        response = client.patch_records(table_id, batch)
        if response.status_code in [200, 201]:
            updated += len(batch)
        else:
            log_error(
                f"  Erreur PATCH labels ({len(batch)} lignes): "
                f"{response.status_code} - {response.text}"
            )

    if updated:
        log(f"  {updated} dossier(s) mis à jour (labels)")

    return updated
