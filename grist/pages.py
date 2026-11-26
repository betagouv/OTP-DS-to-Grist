"""
Arborescence des pages Grist : les pages des tables d'une démarche sont
rangées sous une page parente « N° <numéro> », pliée à sa création, qui
affiche un contenu HTML (`parent_page.html`, où `${demarche_number}` est
remplacé par le numéro de la démarche).

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
from pathlib import Path
from string import Template
from typing import Any

PAGES_TABLE = "_grist_Pages"
TABLES_TABLE = "_grist_Tables"
VIEWS_TABLE = "_grist_Views"
SECTIONS_TABLE = "_grist_Views_section"
COLUMNS_TABLE = "_grist_Tables_column"

# Widget « HTML viewer » de la galerie Grist : affiche, rendu, le HTML de la
# colonne qui lui est reliée, pour la ligne sélectionnée.
HTML_WIDGET_ID = "@gristlabs/widget-renderhtml"
HTML_WIDGET_URL = "https://gristlabs.github.io/grist-widget/renderhtml/index.html"
HTML_WIDGET_ACCESS = "read table"

# Colonne de la table parente qui porte le HTML de la page parente
PARENT_HTML_COLUMN = "Html"
PARENT_TABLE_COLUMNS = [{"id": PARENT_HTML_COLUMN, "type": "Text"}]

_PARENT_PAGE_TEMPLATE = Path(__file__).with_name("parent_page.html")


def get_parent_table_id(demarche_number: int | str) -> str:
    """Table portée par la page parente d'une démarche, qui contient son HTML."""
    return f"Demarche_{demarche_number}"


def get_parent_page_name(demarche_number: int | str) -> str:
    """Nom affiché de la page parente d'une démarche."""
    return f"N° {demarche_number}"


def get_parent_page_html(demarche_number: int | str) -> str:
    """Contenu HTML affiché par la page parente d'une démarche."""
    template = Template(_PARENT_PAGE_TEMPLATE.read_text(encoding="utf-8"))

    return template.substitute(demarche_number=demarche_number)


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


def get_html_widget_actions(
    tables: list[dict[str, Any]],
    sections: list[dict[str, Any]],
    columns: list[dict[str, Any]],
    table_id: str,
    html: str,
) -> list[list[Any]]:
    """
    Actions qui écrivent `html` dans une ligne de la table et le font
    afficher, dans la page de la table, par le widget « HTML viewer » relié à
    sa colonne `Html`.

    La section affichée par la page devient un widget personnalisé : sa
    configuration (`customView`), y compris l'accès en lecture, est celle
    qu'écrit Grist quand on choisit le widget dans la galerie, ce qui évite
    toute demande d'autorisation. Aucune action si la page ou la colonne est
    introuvable.
    """
    table = next(
        (table for table in tables if table["fields"].get("tableId") == table_id), None
    )
    if table is None:
        return []

    view_ref = table["fields"].get("primaryViewId")
    section = next(
        (
            section
            for section in sections
            if section["fields"].get("parentId") == view_ref
            and section["fields"].get("tableRef") == table["id"]
        ),
        None,
    )
    column = next(
        (
            column
            for column in columns
            if column["fields"].get("parentId") == table["id"]
            and column["fields"].get("colId") == PARENT_HTML_COLUMN
        ),
        None,
    )
    if not view_ref or section is None or column is None:
        return []

    widget = {
        "name": "HTML viewer",
        "url": HTML_WIDGET_URL,
        "widgetId": HTML_WIDGET_ID,
        "accessLevel": HTML_WIDGET_ACCESS,
        "columns": [PARENT_HTML_COLUMN],
        "renderAfterReady": True,
    }
    custom_view = {
        "mode": "url",
        "url": HTML_WIDGET_URL,
        "widgetId": HTML_WIDGET_ID,
        "pluginId": "",
        "sectionId": "",
        "access": HTML_WIDGET_ACCESS,
        "renderAfterReady": True,
        "columnsMapping": {PARENT_HTML_COLUMN: column["id"]},
        "widgetDef": widget,
    }

    return [
        ["AddRecord", table_id, None, {PARENT_HTML_COLUMN: html}],
        [
            "UpdateRecord",
            SECTIONS_TABLE,
            section["id"],
            {
                "parentKey": "custom",
                "options": json.dumps({"customView": json.dumps(custom_view)}),
            },
        ],
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
