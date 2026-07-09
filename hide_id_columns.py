# -*- coding: utf-8 -*-
"""
Scanne toutes les tables du doc Grist et cache, dans la première section
de chaque table, toutes les colonnes dont le colId se termine par _id.

Utilise les mêmes variables d'environnement que le reste du projet OTP :
GRIST_BASE_URL, GRIST_API_KEY, GRIST_DOC_ID (chargées via .env).

Usage :
    python hide_id_columns.py
"""

import os
import sys

import requests
from dotenv import load_dotenv


def log(message, level=1, log_level=1):
    if level <= log_level:
        print(message)


def log_error(message):
    print(f"ERREUR: {message}")


class IdColumnHider:
    def __init__(self, base_url, api_key, doc_id):
        base_url = base_url.rstrip("/")
        # GRIST_BASE_URL peut ou non inclure déjà le suffixe /api selon la source
        self.base_url = base_url[:-4] if base_url.endswith("/api") else base_url
        self.doc_id = doc_id
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _api_url(self, path):
        return f"{self.base_url}/api/docs/{self.doc_id}/{path}"

    def _fetch(self, path):
        resp = requests.get(self._api_url(path), headers=self.headers)
        resp.raise_for_status()
        return resp.json()["records"]

    def _hide_field(self, field_id):
        resp = requests.delete(
            self._api_url("tables/_grist_Views_section_field/records"),
            headers=self.headers,
            json={"records": [{"id": field_id}]},
        )
        if resp.status_code in (404, 405):
            resp = requests.post(
                self._api_url("apply"),
                headers=self.headers,
                json=[["RemoveRecord", "_grist_Views_section_field", field_id]],
            )
        resp.raise_for_status()

    def hide_id_columns(self, suffix="_id", table_ids=None):
        """
        Cache dans la première section de chaque table toutes les colonnes
        dont le colId se termine par `suffix`. Retourne (nb_ok, nb_skip).

        table_ids : ensemble optionnel de tableId (ex: {"Demarche_149930_dossiers", ...})
        à traiter. Si None, traite tout le document.
        """
        tables = {
            r["id"]: r["fields"]["tableId"]
            for r in self._fetch("tables/_grist_Tables/records")
        }
        columns = self._fetch("tables/_grist_Tables_column/records")
        sections = self._fetch("tables/_grist_Views_section/records")
        fields = self._fetch("tables/_grist_Views_section_field/records")

        # Index : tableRef -> première section
        first_section = {}
        for r in sections:
            t = r["fields"].get("tableRef")
            if t and t not in first_section:
                first_section[t] = r["id"]

        # Index : (section_id, col_ref) -> field_id
        field_index = {}
        for r in fields:
            key = (r["fields"].get("parentId"), r["fields"].get("colRef"))
            field_index[key] = r["id"]

        nb_ok = 0
        nb_skip = 0
        hidden = []
        skipped = []

        for col in columns:
            col_id = col["fields"].get("colId", "")
            if not col_id.endswith(suffix):
                continue

            table_ref = col["fields"].get("parentId")
            table_name = tables.get(table_ref, f"tableRef={table_ref}")

            if table_ids is not None and table_name not in table_ids:
                continue

            col_ref = col["id"]
            section_id = first_section.get(table_ref)

            if section_id is None:
                log(f"[SKIP] {table_name}.{col_id} — aucune section trouvée", 2)
                skipped.append(f"{table_name}.{col_id}")
                nb_skip += 1
                continue

            field_id = field_index.get((section_id, col_ref))
            if field_id is None:
                log(f"[SKIP] {table_name}.{col_id} — déjà cachée ou absente", 2)
                skipped.append(f"{table_name}.{col_id}")
                nb_skip += 1
                continue

            self._hide_field(field_id)
            log(f"[OK]   {table_name}.{col_id} cachée (section {section_id})", 2)
            hidden.append(f"{table_name}.{col_id}")
            nb_ok += 1

        if hidden:
            log(f"[OK] {len(hidden)} colonne(s) cachée(s) : {', '.join(hidden)}")
        if skipped:
            log(f"[SKIP] {len(skipped)} colonne(s) déjà cachée(s) ou absente(s)")

        return nb_ok, nb_skip


def main():
    load_dotenv(override=True)

    grist_base_url = os.getenv("GRIST_BASE_URL")
    grist_api_key = os.getenv("GRIST_API_KEY")
    grist_doc_id = os.getenv("GRIST_DOC_ID")

    if not all([grist_base_url, grist_api_key, grist_doc_id]):
        log_error("Configuration Grist incomplète dans le fichier .env")
        log("Assurez-vous d'avoir défini GRIST_BASE_URL, GRIST_API_KEY et GRIST_DOC_ID")
        return 1

    hider = IdColumnHider(grist_base_url, grist_api_key, grist_doc_id)
    nb_ok, nb_skip = hider.hide_id_columns()

    log(f"\nTerminé : {nb_ok} colonne(s) cachée(s), {nb_skip} ignorée(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
