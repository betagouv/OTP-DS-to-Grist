"""
Arborescence des pages Grist : les pages des tables d'une démarche sont
rangées sous une page parente « N° <numéro> », pliée à sa création.

Grist n'offre pas d'API pour les pages : l'arbre se lit et s'écrit dans ses
méta-tables. `_grist_Pages` porte l'ordre (`pagePos`) et la profondeur
(`indentation`) ; une page enfant suit sa parente avec une indentation de
plus. Une table mène à sa page par `_grist_Tables.primaryViewId`, qui est le
`viewRef` de la page.

Ce module ne fait que des calculs : il produit les actions à envoyer par
`/apply`, à partir des enregistrements lus dans les méta-tables
(`[{"id": …, "fields": {…}}]`).
"""

import json
from typing import Any

PAGES_TABLE = "_grist_Pages"
TABLES_TABLE = "_grist_Tables"
VIEWS_TABLE = "_grist_Views"

# Colonnes de la table parente : son contenu est sans importance, mais
# `POST /tables` refuse une table sans colonne.
PARENT_TABLE_COLUMNS = [{"id": "A", "type": "Text"}]


def get_parent_table_id(demarche_number: int | str) -> str:
    """Table vide portée par la page parente d'une démarche."""
    return f"Demarche_{demarche_number}"


def get_parent_page_name(demarche_number: int | str) -> str:
    """Nom affiché de la page parente d'une démarche."""
    return f"N° {demarche_number}"


def is_demarche_table(table_id: str, demarche_number: int | str) -> bool:
    """Indique si la table appartient à la démarche (hors table parente)."""
    return table_id.lower().startswith(f"demarche_{demarche_number}_")


def get_folded_page_actions(
    pages: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    table_id: str,
    page_name: str,
) -> list[list[Any]]:
    """
    Actions qui remplacent la page d'une table par une page pliée, à la même
    place, et la renomment.

    Grist ne lit l'état plié qu'à la création d'une page : poser `collapsed`
    sur la page existante ne serait visible qu'après rechargement du
    document. La page est donc retirée puis recréée, déjà pliée, sur la même
    vue ; retirer une page ne supprime ni sa vue ni sa table.
    """
    page = _get_table_page(pages, tables, table_id)
    if page is None:
        return []

    view_ref = page["fields"]["viewRef"]

    return [
        ["RemoveRecord", PAGES_TABLE, page["id"]],
        [
            "AddRecord",
            PAGES_TABLE,
            None,
            {
                "viewRef": view_ref,
                "indentation": page["fields"]["indentation"],
                "pagePos": page["fields"]["pagePos"],
                "options": json.dumps({"collapsed": True}),
            },
        ],
        ["UpdateRecord", VIEWS_TABLE, view_ref, {"name": page_name}],
    ]


def get_page_attachment_actions(
    pages: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    parent_table: str,
    child_table: str,
) -> list[list[Any]]:
    """
    Actions qui rangent la page de `child_table` en dernière enfant de la page
    de `parent_table`.

    L'indentation d'une page se lit par rapport à celle qui la précède :
    déplacer une page impose de réécrire l'ordre de toutes les pages, en un
    seul envoi. Aucune action si l'une des deux pages est introuvable.
    """
    parent_page = _get_table_page(pages, tables, parent_table)
    child_page = _get_table_page(pages, tables, child_table)
    if parent_page is None or child_page is None:
        return []

    ordered = [
        page
        for page in sorted(pages, key=lambda page: page["fields"]["pagePos"])
        if page["id"] != child_page["id"]
    ]
    parent_index = next(
        index for index, page in enumerate(ordered) if page["id"] == parent_page["id"]
    )
    parent_indentation = parent_page["fields"]["indentation"]
    insert_index = _get_subtree_end_position(ordered, parent_index, parent_indentation)
    ordered.insert(insert_index, child_page)

    indentations = [
        parent_indentation + 1
        if page["id"] == child_page["id"]
        else page["fields"]["indentation"]
        for page in ordered
    ]

    return [
        [
            "BulkUpdateRecord",
            PAGES_TABLE,
            [page["id"] for page in ordered],
            {
                "pagePos": list(range(1, len(ordered) + 1)),
                "indentation": indentations,
            },
        ]
    ]


# --- Helpers privés (module) ---


def _get_table_page(
    pages: list[dict[str, Any]], tables: list[dict[str, Any]], table_id: str
) -> dict[str, Any] | None:
    """Page de la vue principale d'une table, ou None si elle n'en a pas."""
    view_ref = next(
        (
            table["fields"].get("primaryViewId")
            for table in tables
            if table["fields"].get("tableId") == table_id
        ),
        None,
    )
    if not view_ref:
        return None

    return next(
        (page for page in pages if page["fields"].get("viewRef") == view_ref), None
    )


def _get_subtree_end_position(
    ordered: list[dict[str, Any]], parent_index: int, parent_indentation: int
) -> int:
    """Position qui suit la dernière descendante de la page parente."""
    index = parent_index + 1
    while (
        index < len(ordered)
        and ordered[index]["fields"]["indentation"] > parent_indentation
    ):
        index += 1

    return index
