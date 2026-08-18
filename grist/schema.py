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
