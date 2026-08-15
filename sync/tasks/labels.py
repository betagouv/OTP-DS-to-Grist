# -*- coding: utf-8 -*-
"""
Rafraîchissement des labels (étiquettes) des dossiers dans Grist.
Ce script interroge tous les dossiers de la démarche avec une requête minimaliste
(number + labels) et met à jour les seules lignes dont les labels ont changé.

Utilisation autonome (depuis la racine du projet) :
    python -m sync.tasks.labels

Variables d'environnement requises :
    GRIST_BASE_URL, GRIST_API_KEY, GRIST_DOC_ID, DEMARCHE_NUMBER
"""

import json
import os
import sys
import time

import requests

from queries_graphql import get_demarche_dossiers_labels_only

BATCH_SIZE = 500


def _build_label_fields(labels):
    """Construit label_names / labels_json à partir des labels d'un dossier."""
    if not labels:
        return {"label_names": "", "labels_json": ""}

    label_names = [label.get("name", "") for label in labels if label.get("name")]

    labels_with_colors = [
        {
            "id": label.get("id", ""),
            "name": label.get("name", ""),
            "color": label.get("color", ""),
        }
        for label in labels
        if label.get("name") and label.get("color")
    ]

    return {
        "label_names": ", ".join(label_names) if label_names else "",
        "labels_json": (
            json.dumps(labels_with_colors, ensure_ascii=False)
            if labels_with_colors
            else ""
        ),
    }


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
    url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/records"
    updated = 0

    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        response = requests.patch(url, headers=client.headers, json={"records": batch})
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

        fields = _build_label_fields(dossier.get("labels"))
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


def main():
    from dotenv import load_dotenv

    from grist.client import GristClient

    load_dotenv(override=True)

    grist_base_url = os.getenv("GRIST_BASE_URL")
    grist_api_key = os.getenv("GRIST_API_KEY")
    grist_doc_id = os.getenv("GRIST_DOC_ID")
    demarche_number = os.getenv("DEMARCHE_NUMBER")

    if not all([grist_base_url, grist_api_key, grist_doc_id, demarche_number]):
        print(
            "Configuration incomplète : GRIST_BASE_URL, GRIST_API_KEY, "
            "GRIST_DOC_ID et DEMARCHE_NUMBER sont requis dans le fichier .env"
        )
        return 1

    demarche_number = int(demarche_number)
    table_id = os.getenv("TABLE_DOSSIERS", f"Demarche_{demarche_number}_dossiers")

    client = GristClient(grist_base_url, grist_api_key, grist_doc_id)
    sync_labels_for_demarche(client, table_id, demarche_number)

    return 0


if __name__ == "__main__":
    sys.exit(main())
