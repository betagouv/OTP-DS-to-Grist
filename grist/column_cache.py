from utils.log import log_verbose


class ColumnCache:
    """
    Met en cache les colonnes des tables Grist pour éviter des requêtes répétées à l'API.
    La récupération HTTP est déléguée au client Grist.
    """

    def __init__(self, client):
        self.client = client
        self.columns_cache: dict[str, dict[str, str]] = {}

    def get_columns(self, table_id: str, force_refresh: bool = False) -> set[str]:
        """
        Retourne les IDs des colonnes d'une table, en utilisant le cache si disponible.

        Args:
            table_id: ID de la table Grist
            force_refresh: Force la récupération depuis l'API même si en cache

        Returns:
            set: Ensemble des IDs de colonnes
        """
        if table_id not in self.columns_cache or force_refresh:
            log_verbose(f"Récupération des colonnes pour la table {table_id}")
            self.columns_cache[table_id] = self.client.get_columns(table_id)
            log_verbose(
                f"  {len(self.columns_cache[table_id])} colonnes en cache pour {table_id}"
            )

        return set(self.columns_cache[table_id])
