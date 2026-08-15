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
from typing import Any

from dotenv import load_dotenv

from grist.client import GristClient


def log(message, level=1, log_level=1):
    if level <= log_level:
        print(message)


def log_error(message):
    print(f"ERREUR: {message}")


class IdColumnHider:
    def __init__(self, client: GristClient) -> None:
        self.client = client

    def hide_id_columns(
        self, suffix: str = "_id", table_ids: set[str] | None = None
    ) -> tuple[int, int]:
        """
        Cache dans la première section de chaque table toutes les colonnes
        dont le colId se termine par `suffix`. Retourne (nb_ok, nb_skip).

        table_ids : ensemble optionnel de tableId (ex: {"Demarche_149930_dossiers", ...})
        à traiter. Si None, traite tout le document.
        """
        tables = {
            r["id"]: r["fields"]["tableId"] for r in self._fetch("_grist_Tables")
        }
        columns = self._fetch("_grist_Tables_column")
        sections = self._fetch("_grist_Views_section")
        fields = self._fetch("_grist_Views_section_field")

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
                skipped.append(f"{table_name}.{col_id}")
                nb_skip += 1
                continue

            field_id = field_index.get((section_id, col_ref))
            if field_id is None:
                skipped.append(f"{table_name}.{col_id}")
                nb_skip += 1
                continue

            self._hide_field(field_id)
            hidden.append(f"{table_name}.{col_id}")
            nb_ok += 1

        if hidden:
            hidden_tables = sorted({h.split(".")[0] for h in hidden})
            log(
                f"[OK] {len(hidden)} colonne(s) cachée(s) sur : {', '.join(hidden_tables)}"
            )
        if skipped:
            skipped_tables = sorted({s.split(".")[0] for s in skipped})
            log(
                f"[SKIP] {len(skipped)} colonne(s) sur : {', '.join(skipped_tables)}"
            )

        return nb_ok, nb_skip

    def _fetch(self, table_id: str) -> list[dict[str, Any]]:
        return self.client.get_records(table_id).json()["records"]

    def _hide_field(self, field_id: int) -> None:
        self.client.delete_records(
            "_grist_Views_section_field", [field_id]
        ).raise_for_status()


def main() -> int:
    load_dotenv(override=True)

    grist_base_url = os.getenv("GRIST_BASE_URL")
    grist_api_key = os.getenv("GRIST_API_KEY")
    grist_doc_id = os.getenv("GRIST_DOC_ID")

    if not all([grist_base_url, grist_api_key, grist_doc_id]):
        log_error("Configuration Grist incomplète dans le fichier .env")
        log(
            "Assurez-vous d'avoir défini GRIST_BASE_URL, GRIST_API_KEY et GRIST_DOC_ID"
        )
        return 1

    client = GristClient(grist_base_url, grist_api_key, grist_doc_id)
    hider = IdColumnHider(client)
    nb_ok, nb_skip = hider.hide_id_columns()

    log(f"\nTerminé : {nb_ok} colonne(s) cachée(s), {nb_skip} ignorée(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
