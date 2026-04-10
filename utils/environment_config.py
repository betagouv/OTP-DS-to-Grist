import os

def build_environment(config: dict) -> dict:
    """
    Construit l'environnement pour subprocess à partir de la config.
    
    Args:
        config: Dict avec les paramètres de synchronisation
    
    Returns:
        Dict des variables d'environnement à passer au subprocess
    """
    env = os.environ.copy()
    
    # Appliquer les filtres
    if config.get("filter_date_start"):
        env["DATE_DEPOT_DEBUT"] = config["filter_date_start"]
    if config.get("filter_date_end"):
        env["DATE_DEPOT_FIN"] = config["filter_date_end"]
    if config.get("filter_statuses"):
        env["STATUTS_DOSSIERS"] = config["filter_statuses"]
    if config.get("filter_groups"):
        env["GROUPES_INSTRUCTEURS"] = config["filter_groups"]
    
    # Appliquer le mapping
    mapping = {
        "ds_api_token": "DEMARCHES_API_TOKEN",
        "demarche_number": "DEMARCHE_NUMBER",
        "grist_base_url": "GRIST_BASE_URL",
        "grist_api_key": "GRIST_API_KEY",
        "grist_doc_id": "GRIST_DOC_ID",
        "grist_user_id": "GRIST_USER_ID",
    }
    for key, env_key in mapping.items():
        if key in config:
            env[env_key] = config[key]
    
    return env
