"""
Masquage des colonnes techniques dans les vues Grist.

Grist ne connaît pas d'action « masquer une colonne » : une colonne n'apparaît
dans une vue que si `_grist_Views_section_field` contient une ligne de champ
pour elle. Masquer revient donc à supprimer cette ligne — l'action utilisateur
`BulkRemoveRecord` sur cette table, celle de l'interface — la colonne et ses
données restant intactes. Le masquage reste ainsi réversible depuis
l'interface, où le ré-afficher rejoue un `AddVisibleColumn`.

Seules les colonnes de la vue principale de chaque table sont concernées : c'est
la seule vue qu'ouvre l'agent, et Grist refuse de modifier les sections brutes
comme les fiches de détail.
"""

from grist.client import GristClient
from utils.log import log, log_error, log_verbose

ID_SUFFIX = "_id"
VIEW_FIELDS_TABLE = "_grist_Views_section_field"

_VIEW_FIELDS_QUERY = """
SELECT f.id AS fieldId, t.tableId, c.colId
FROM _grist_Tables t
JOIN _grist_Views_section s ON s.parentId = t.primaryViewId
JOIN _grist_Views_section_field f ON f.parentId = s.id
JOIN _grist_Tables_column c ON c.id = f.colRef
WHERE t.primaryViewId <> 0
"""


def hide_columns_with_id(client: GristClient) -> int:
    """
    Masque les colonnes techniques `_id` des vues principales du document.

    Args:
        client: Instance de GristClient.

    Returns:
        int: Nombre de colonnes masquées.
    """
    return hide_columns_ending_with(client, suffix=ID_SUFFIX)


def hide_columns_ending_with(client: GristClient, suffix: str) -> int:
    """
    Masque les colonnes dont le nom se termine par `suffix`, vue principale de
    chaque table, en un seul aller-retour : une lecture pour trouver les lignes
    de champ concernées, une écriture pour les supprimer.

    Le filtrage des résultats est fait ici et non dans le SQL : Grist n'accepte
    que des SELECT dans `/sql`, sans paramètres, alors que le suffixe est
    fourni par l'appelant.

    Args:
        client: Instance de GristClient.
        suffix: Suffixe des noms de colonnes à masquer.

    Returns:
        int: Nombre de colonnes masquées.
    """
    columns = [
        line
        for line in client.run_sql(_VIEW_FIELDS_QUERY)
        if line.get("colId", "").endswith(suffix)
    ]

    if not columns:
        log_verbose(f"Aucune colonne terminée par « {suffix} » à masquer.")
        return 0

    labels = ", ".join(f"{line.get('tableId', '')}.{line['colId']}" for line in columns)
    field_ids = [line["fieldId"] for line in columns]
    response = client.apply_user_actions(
        [["BulkRemoveRecord", VIEW_FIELDS_TABLE, field_ids]]
    )

    if response.status_code not in (200, 201):
        log_error(f"Erreur {response.status_code}: {response.text}")
        response.raise_for_status()

    log(f"Colonnes masquées dans la vue principale : {labels}")
    return len(columns)
