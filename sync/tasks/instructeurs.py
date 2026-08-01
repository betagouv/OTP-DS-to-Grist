# -*- coding: utf-8 -*-
"""
Synchronisation de la table Instructeurs (niveau démarche).

Récupère les instructeurs de la démarche via l'API DN (groupeInstructeurs) et
met la table Grist à jour par upsert sur la clé composite
`instructeur_id` + `groupe_instructeur_id` : créations, mises à jour, suppressions.

Utilisation autonome (depuis la racine du projet) :
    python -m sync.tasks.instructeurs

Variables d'environnement requises :
    GRIST_BASE_URL, GRIST_API_KEY, GRIST_DOC_ID, DEMARCHE_NUMBER
"""

import os
import sys
import time

import requests

from queries_extract import extract_instructeurs_from_demarche

# Champs comparés pour décider si un enregistrement existant doit être mis à jour
COMPARED_FIELDS = [
    "groupe_instructeur_id",
    "groupe_instructeur_number",
    "groupe_instructeur_label",
    "instructeur_email",
]


def _composite_key(instructeur_id, groupe_instructeur_id):
    """Clé unique d'un instructeur au sein d'un groupe."""
    return f"{instructeur_id}_{groupe_instructeur_id}"


def _fetch_existing_records(client, table_id):
    """Récupère les enregistrements actuels de la table instructeurs.

    Raises:
        RuntimeError: si Grist ne répond pas correctement. Confondre un échec de
            lecture avec une table vide provoquerait la recréation de tous les
            instructeurs, donc des doublons.
    """
    url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/records"
    response = requests.get(url, headers=client.headers)

    if response.status_code != 200:
        raise RuntimeError(
            f"Lecture de la table {table_id} impossible : "
            f"{response.status_code} - {response.text}"
        )

    return response.json().get("records", [])


def _build_existing_map(existing_records):
    """Indexe les enregistrements Grist existants par clé composite."""
    existing_map = {}
    for record in existing_records:
        fields = record.get("fields", {})
        instructeur_id = fields.get("instructeur_id")
        groupe_id = fields.get("groupe_instructeur_id")
        if instructeur_id and groupe_id:
            existing_map[_composite_key(instructeur_id, groupe_id)] = {
                "grist_id": record.get("id"),
                "fields": fields,
            }
    return existing_map


def _diff_records(existing_map, new_map):
    """Compare l'état Grist et l'état DN, et retourne les enregistrements
    à supprimer, à mettre à jour et à créer."""
    to_delete = [
        data["grist_id"] for key, data in existing_map.items() if key not in new_map
    ]

    to_update = []
    to_create = []

    for key, new_data in new_map.items():
        if key not in existing_map:
            to_create.append(new_data)
            continue

        existing_fields = existing_map[key]["fields"]
        if any(existing_fields.get(f) != new_data.get(f) for f in COMPARED_FIELDS):
            to_update.append({"id": existing_map[key]["grist_id"], "fields": new_data})

    return to_delete, to_update, to_create


def _apply_records_diff(
    client, table_id, to_delete, to_update, to_create, log, log_error
):
    """Applique les suppressions, mises à jour et créations dans Grist."""
    url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/records"
    operations_count = 0

    if to_delete:
        response = requests.post(
            f"{url}/delete", headers=client.headers, json=to_delete
        )
        if response.status_code in [200, 201]:
            log(f"  🗑️  {len(to_delete)} instructeur(s) supprimé(s)")
            operations_count += len(to_delete)
        else:
            log_error(f"  Erreur suppression instructeurs: {response.text}")

    if to_update:
        response = requests.patch(
            url, headers=client.headers, json={"records": to_update}
        )
        if response.status_code in [200, 201]:
            log(f"  {len(to_update)} instructeur(s) mis à jour")
            operations_count += len(to_update)
        else:
            log_error(f"  Erreur mise à jour instructeurs: {response.text}")

    if to_create:
        payload = {"records": [{"fields": r} for r in to_create]}
        response = requests.post(url, headers=client.headers, json=payload)
        if response.status_code in [200, 201]:
            log(f"  {len(to_create)} instructeur(s) créé(s)")
            operations_count += len(to_create)
        else:
            log_error(f"  Erreur création instructeurs: {response.text}")

    return operations_count


def sync_instructeurs(client, table_id, demarche_number, log=print, log_error=print):
    """
    Synchronise la table Instructeurs d'une démarche dans Grist.

    Args:
        client:          Instance GristClient
        table_id:        ID de la table instructeurs
        demarche_number: Numéro de la démarche
        log:             Fonction de log du processeur principal
        log_error:       Fonction de log d'erreur

    Returns:
        dict: {"total": int, "created": int, "updated": int, "deleted": int}
    """
    start_time = time.time()
    result = {"total": 0, "created": 0, "updated": 0, "deleted": 0}
    log(f"  Récupération des instructeurs de la démarche {demarche_number}...")

    instructeurs_records = extract_instructeurs_from_demarche(demarche_number)

    if not instructeurs_records:
        log("  Aucun instructeur trouvé pour cette démarche")
        return result

    log(f"  {len(instructeurs_records)} instructeur(s) trouvé(s)")

    existing_map = _build_existing_map(_fetch_existing_records(client, table_id))
    new_map = {
        _composite_key(r["instructeur_id"], r["groupe_instructeur_id"]): r
        for r in instructeurs_records
    }

    to_delete, to_update, to_create = _diff_records(existing_map, new_map)

    operations_count = _apply_records_diff(
        client, table_id, to_delete, to_update, to_create, log, log_error
    )

    if operations_count == 0:
        log("  Table instructeurs à jour (aucun changement)")
    else:
        log(f"  Table instructeurs synchronisée ({operations_count} opération(s))")

    log(f"[TIMING] Instructeurs synchronisés en {time.time() - start_time:.1f}s")

    result.update(
        {
            "total": len(instructeurs_records),
            "created": len(to_create),
            "updated": len(to_update),
            "deleted": len(to_delete),
        }
    )

    return result


def main():
    from dotenv import load_dotenv

    from grist_processor_working_all import GristClient

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
    table_id = os.getenv(
        "TABLE_INSTRUCTEURS", f"Demarche_{demarche_number}_instructeurs"
    )

    client = GristClient(grist_base_url, grist_api_key, grist_doc_id)
    sync_instructeurs(client, table_id, demarche_number)

    return 0


if __name__ == "__main__":
    sys.exit(main())
