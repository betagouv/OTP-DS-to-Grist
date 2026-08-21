"""
Définitions de colonnes Grist pour les tables secondaires
(demandeurs, instructeurs, avis).
"""


def create_demandeurs_pp_columns():
    """
    Crée les colonnes pour la table demandeurs (PersonnePhysique)

    Returns:
        list: Définitions des colonnes Grist
    """
    return [
        {"id": "dossier_number", "type": "Int"},
        {"id": "type", "type": "Text"},
        {"id": "civilite", "type": "Text"},
        {"id": "nom", "type": "Text"},
        {"id": "prenom", "type": "Text"},
        {"id": "email", "type": "Text"},
        {"id": "usager_email", "type": "Text"},
        {"id": "prenom_mandataire", "type": "Text"},
        {"id": "nom_mandataire", "type": "Text"},
        {"id": "depose_par_un_tiers", "type": "Bool"},
        {"id": "connection_usager", "type": "Text"},
    ]


def create_demandeurs_pm_columns():
    """
    Crée les colonnes pour la table demandeurs (PersonneMorale)
    avec tous les champs enrichis SIRENE

    Returns:
        list: Définitions des colonnes Grist
    """
    return [
        # Métadonnées
        {"id": "dossier_number", "type": "Int"},
        {"id": "type", "type": "Text"},
        {"id": "usager_email", "type": "Text"},
        # Identifiants de base
        {"id": "siret", "type": "Text"},
        {"id": "siren", "type": "Text"},
        {"id": "siege_social", "type": "Bool"},
        {"id": "naf", "type": "Text"},
        {"id": "libelle_naf", "type": "Text"},
        # Entreprise (champs enrichis SIRENE)
        {"id": "raison_sociale", "type": "Text"},
        {"id": "nom_commercial", "type": "Text"},
        {"id": "forme_juridique", "type": "Text"},
        {"id": "forme_juridique_code", "type": "Text"},
        {"id": "capital_social", "type": "Text"},
        {"id": "code_effectif_entreprise", "type": "Text"},
        {"id": "numero_tva_intracommunautaire", "type": "Text"},
        {"id": "date_creation", "type": "Date"},
        {"id": "etat_administratif", "type": "Text"},
        # Association (si applicable)
        {"id": "rna", "type": "Text"},
        {"id": "titre_association", "type": "Text"},
        {"id": "objet_association", "type": "Text"},
        {"id": "date_creation_association", "type": "Date"},
        {"id": "date_declaration_association", "type": "Date"},
        {"id": "date_publication_association", "type": "Date"},
        # Adresse enrichie
        {"id": "adresse_label", "type": "Text"},
        {"id": "adresse_type", "type": "Text"},
        {"id": "street_address", "type": "Text"},
        {"id": "street_number", "type": "Text"},
        {"id": "street_name", "type": "Text"},
        {"id": "code_postal", "type": "Text"},
        {"id": "ville", "type": "Text"},
        {"id": "code_insee_ville", "type": "Text"},
        {"id": "departement", "type": "Text"},
        {"id": "code_departement", "type": "Text"},
        {"id": "region", "type": "Text"},
        {"id": "code_region", "type": "Text"},
        {"id": "connection_usager", "type": "Text"},
    ]


def create_instructeurs_columns():
    """
    Crée les colonnes pour la table instructeurs (niveau démarche)
    1 ligne = 1 instructeur dans 1 groupe

    Returns:
        list: Définitions des colonnes Grist
    """
    return [
        # Groupe instructeur
        {"id": "groupe_instructeur_id", "type": "Text"},
        {"id": "groupe_instructeur_number", "type": "Int"},
        {"id": "groupe_instructeur_label", "type": "Text"},
        # Instructeur
        {"id": "instructeur_id", "type": "Text"},
        {"id": "instructeur_email", "type": "Text"},
    ]


def create_avis_columns():
    return [
        {"id": "dossier_number", "type": "Int"},
        {"id": "avis_id", "type": "Text"},
        {"id": "instructeur_email", "type": "Text"},
        {"id": "expert_email", "type": "Text"},
        {"id": "date_question", "type": "Text"},
        {"id": "date_reponse", "type": "Text"},
        {"id": "question", "type": "Text"},
        {"id": "reponse", "type": "Text"},
    ]


def update_grist_tables_from_schema(client, demarche_number, column_types):
    """
    Met à jour les tables Grist existantes en fonction du schéma actuel de la démarche,
    en ajoutant les nouvelles colonnes sans supprimer les données existantes.

     NOUVEAU : Crée une table séparée pour chaque bloc répétable

    Args:
        client: Instance GristClient
        demarche_number: Numéro de la démarche
        column_types: Définitions des colonnes depuis create_columns_from_schema

    Returns:
        dict: IDs des tables créées/mises à jour
    """
    from utils.log import log, log_error

    try:
        log(
            f"Mise à jour des tables Grist pour la démarche {demarche_number} d'après le schéma..."
        )

        # Noms des tables
        dossier_table_id = f"Demarche_{demarche_number}_dossiers"
        champ_table_id = f"Demarche_{demarche_number}_champs"
        annotation_table_id = f"Demarche_{demarche_number}_annotations"
        has_repetable_blocks = column_types.get("has_repetable_blocks", False)

        # Récupérer toutes les tables existantes
        tables = client.list_tables()

        #  CORRECTION : Extraire la liste des tables
        if isinstance(tables, dict) and "tables" in tables:
            tables = tables["tables"]

        # Trouver les tables existantes
        dossier_table = None
        champ_table = None
        annotation_table = None

        for table in tables:
            table_id = table.get("id", "").lower()
            if table_id == dossier_table_id.lower():
                dossier_table = table
                dossier_table_id = table.get("id")
                log(f"Table dossiers existante trouvée avec l'ID {dossier_table_id}")
            elif table_id == champ_table_id.lower():
                champ_table = table
                champ_table_id = table.get("id")
                log(f"Table champs existante trouvée avec l'ID {champ_table_id}")
            elif table_id == annotation_table_id.lower():
                annotation_table = table
                annotation_table_id = table.get("id")
                log(
                    f"Table annotations existante trouvée avec l'ID {annotation_table_id}"
                )

        # Fonction pour ajouter les colonnes manquantes à une table
        def add_missing_columns(table_id, all_columns):
            if not table_id:
                return

            existing_columns = {col["id"] for col in client.get_table_columns(table_id)}
            missing = [col for col in all_columns if col["id"] not in existing_columns]

            if missing:
                log(
                    f"Ajout de {len(missing)} colonnes manquantes à la table {table_id}"
                )
                client.add_columns(table_id, missing)

        # Créer ou mettre à jour la table des dossiers
        if not dossier_table:
            log(f"Création de la table {dossier_table_id}")
            dossier_table_result = client.create_table(
                dossier_table_id, column_types["dossier"]
            )
            dossier_table = dossier_table_result["tables"][0]
            dossier_table_id = dossier_table.get("id")
        else:
            add_missing_columns(dossier_table_id, column_types["dossier"])

        # Créer ou mettre à jour la table des champs
        if not champ_table:
            log(f"Création de la table {champ_table_id}")
            base_columns = [
                {"id": "dossier_number", "type": "Int"},
                {"id": "champ_id", "type": "Text"},
            ]
            champ_table_result = client.create_table(champ_table_id, base_columns)
            champ_table = champ_table_result["tables"][0]
            champ_table_id = champ_table.get("id")

            # Ajouter toutes les colonnes spécifiques
            add_missing_columns(champ_table_id, column_types["champs"])
        else:
            add_missing_columns(champ_table_id, column_types["champs"])

        # Créer ou mettre à jour la table des annotations
        if not annotation_table:
            # Ne créer que s'il y a des annotations (> 1 car dossier_number toujours présent)
            if len(column_types["annotations"]) > 1:
                log(f"Création de la table {annotation_table_id}")
                base_columns = [{"id": "dossier_number", "type": "Int"}]
                annotation_table_result = client.create_table(
                    annotation_table_id, base_columns
                )
                annotation_table = annotation_table_result["tables"][0]
                annotation_table_id = annotation_table.get("id")

                # Ajouter toutes les colonnes spécifiques
                add_missing_columns(annotation_table_id, column_types["annotations"])
            else:
                log(f"Aucune annotation - table {annotation_table_id} non créée")
                annotation_table_id = None
        else:
            add_missing_columns(annotation_table_id, column_types["annotations"])

        # Créer ou mettre à jour les tables des blocs répétables (une par bloc)
        repetable_table_ids = {}
        if has_repetable_blocks and "repetable_blocks" in column_types:
            for block_key, block_info in column_types["repetable_blocks"].items():
                table_id = f"Demarche_{demarche_number}_repetable_{block_key}"

                # Chercher si la table existe déjà
                existing_table = None
                for table in tables:
                    if table.get("id", "").lower() == table_id.lower():
                        existing_table = table
                        table_id = table.get("id")
                        log(
                            f"Table répétable '{block_info['original_label']}' existante trouvée: {table_id}"
                        )
                        break

                if not existing_table:
                    log(
                        f"Création de la table {table_id} pour le bloc '{block_info['original_label']}'"
                    )
                    table_result = client.create_table(table_id, block_info["columns"])
                    table_id = table_result["tables"][0].get("id")
                else:
                    # Ajouter les colonnes manquantes
                    add_missing_columns(table_id, block_info["columns"])

                repetable_table_ids[block_key] = table_id

        # Créer ou mettre à jour la table demandeurs
        log("Création/mise à jour de la table demandeurs...")
        demandeurs_table_id = f"Demarche_{demarche_number}_demandeurs"

        from sync.demandeurs import create_demandeurs_columns

        demandeurs_columns, demandeur_type = create_demandeurs_columns(demarche_number)
        log(f"Type de demandeur: {demandeur_type} - {len(demandeurs_columns)} colonnes")

        # Chercher si la table existe
        demandeurs_table = None
        for table in tables:
            if table.get("id", "").lower() == demandeurs_table_id.lower():
                demandeurs_table = table
                demandeurs_table_id = table.get("id")
                log(f"Table demandeurs existante trouvée: {demandeurs_table_id}")
                break

        # Créer ou mettre à jour
        if not demandeurs_table:
            log(f"Création de la table {demandeurs_table_id} (type: {demandeur_type})")
            demandeurs_table_result = client.create_table(
                demandeurs_table_id, demandeurs_columns
            )
            demandeurs_table = demandeurs_table_result["tables"][0]
            demandeurs_table_id = demandeurs_table.get("id")
        else:
            log("Mise à jour des colonnes de la table demandeurs")
            add_missing_columns(demandeurs_table_id, demandeurs_columns)

        # Créer/mettre à jour la table instructeurs
        log("Création/mise à jour de la table instructeurs...")
        instructeurs_table_id = f"Demarche_{demarche_number}_instructeurs"
        instructeurs_table = next(
            (t for t in tables if t.get("id") == instructeurs_table_id), None
        )

        if not instructeurs_table:
            log(f"Création de la table {instructeurs_table_id}")
            columns = create_instructeurs_columns()
            instructeurs_table_result = client.create_table(
                instructeurs_table_id, columns
            )
            instructeurs_table = instructeurs_table_result["tables"][0]
            instructeurs_table_id = instructeurs_table.get("id")
        else:
            log("Mise à jour des colonnes de la table instructeurs")
            columns = create_instructeurs_columns()
            add_missing_columns(instructeurs_table_id, columns)

        # Créer/mettre à jour la table avis (seulement si elle existe déjà)
        avis_table_id = f"Demarche_{demarche_number}_avis"
        avis_table = next((t for t in tables if t.get("id") == avis_table_id), None)

        if avis_table:
            log(f"Table avis existante trouvée: {avis_table_id}")
            add_missing_columns(avis_table_id, create_avis_columns())
        else:
            log("Table avis non créée (sera créée au premier avis détecté)")
            avis_table_id = None

        # Retourner les IDs des tables
        result = {
            "dossiers": dossier_table_id,
            "champs": champ_table_id,
            "demandeurs": demandeurs_table_id,
            "demandeur_type": demandeur_type,
            "instructeurs": instructeurs_table_id,
            "avis": avis_table_id,  # None si pas encore créée
        }

        # Ajouter annotations seulement si la table existe
        if annotation_table_id:
            result["annotations"] = annotation_table_id

        # Ajouter les blocs répétables si présents
        if has_repetable_blocks:
            result["repetable_blocks"] = repetable_table_ids

        # Créer ou mettre à jour la table Sync_metadata
        sync_metadata_table_id = "Sync_metadata"
        sync_metadata_columns = [
            {"id": "demarche_number", "type": "Int"},
            {"id": "last_sync_at", "type": "Text"},
            {"id": "updated_since_cursor", "type": "Text"},
            {"id": "deleted_since_cursor", "type": "Text"},
            {"id": "deleted_after_cursor", "type": "Text"},
            {"id": "last_sync_status", "type": "Text"},
            {"id": "last_sync_duration", "type": "Numeric"},
            {
                "id": "force_full_sync",
                "type": "Bool",
                "fields": {"type": "Bool", "isFormula": False, "formula": ""},
            },
        ]

        # Recharger la liste des tables pour les inclure celles créées pendant cette exécution
        fresh_tables = client.list_tables()
        if isinstance(fresh_tables, dict) and "tables" in fresh_tables:
            fresh_tables = fresh_tables["tables"]
        sync_table = next(
            (t for t in fresh_tables if t.get("id") == sync_metadata_table_id), None
        )
        if not sync_table:
            log(f"Création de la table {sync_metadata_table_id}")
            client.create_table(sync_metadata_table_id, sync_metadata_columns)
        else:
            add_missing_columns(sync_metadata_table_id, sync_metadata_columns)

        # BUG CONNU : Le bloc ci-dessous est une copie verbatim du bloc Sync_metadata
        # ci-dessus (lignes ~422-450). Il exécute la même opération deux fois.
        # À corriger lors du prochain refactoring de cette fonction.
        sync_metadata_table_id = "Sync_metadata"
        sync_metadata_columns = [
            {"id": "demarche_number", "type": "Int"},
            {"id": "last_sync_at", "type": "Text"},
            {"id": "updated_since_cursor", "type": "Text"},
            {"id": "deleted_since_cursor", "type": "Text"},
            {"id": "deleted_after_cursor", "type": "Text"},
            {"id": "last_sync_status", "type": "Text"},
            {"id": "last_sync_duration", "type": "Numeric"},
            {
                "id": "force_full_sync",
                "type": "Bool",
                "fields": {"type": "Bool", "isFormula": False, "formula": ""},
            },
        ]

        fresh_tables = client.list_tables()
        if isinstance(fresh_tables, dict) and "tables" in fresh_tables:
            fresh_tables = fresh_tables["tables"]
        sync_table = next(
            (t for t in fresh_tables if t.get("id") == sync_metadata_table_id), None
        )
        if not sync_table:
            log(f"Création de la table {sync_metadata_table_id}")
            client.create_table(sync_metadata_table_id, sync_metadata_columns)
        else:
            add_missing_columns(sync_metadata_table_id, sync_metadata_columns)

        result["sync_metadata"] = sync_metadata_table_id

        log("Mise à jour des tables terminée avec succès")
        return result

    except Exception as e:
        log_error(f"Erreur lors de la mise à jour des tables: {str(e)}")
        raise
