import requests
import json
from typing import Dict, Any, List, Optional
from queries_config import API_TOKEN, API_URL

# Requêtes GraphQL (fragmentées en quelques constantes)
# Pour les fragments communs
COMMON_FRAGMENTS = """
fragment PersonneMoraleFragment on PersonneMorale {
    siret
    siegeSocial
    naf
    libelleNaf
    address {
        ...AddressFragment
    }
    entreprise {
        siren
        raisonSociale
        nomCommercial
    }
}

fragment PersonneMoraleIncompleteFragment on PersonneMoraleIncomplete {
    siret
}

fragment PersonnePhysiqueFragment on PersonnePhysique {
    civilite
    nom
    prenom
    email
}

fragment AddressFragment on Address {
    label
    type
    streetAddress
    postalCode
    cityName
}

fragment FileFragment on File {
    __typename
    filename
    contentType
    checksum
    byteSize: byteSizeBigInt
    url
    createdAt
}

fragment GeoAreaFragment on GeoArea {
    id
    source
    description
    geometry @include(if: $includeGeometry) {
        type
        coordinates
    }
    ... on ParcelleCadastrale {
        commune
        numero
        section
        prefixe
        surface
    }
}
"""

# Pour les types spécialisés
SPECIALIZED_FRAGMENTS = """
fragment PaysFragment on Pays {
    name
    code
}

fragment RegionFragment on Region {
    name
    code
}

fragment DepartementFragment on Departement {
    name
    code
}

fragment EpciFragment on Epci {
    name
    code
}

fragment CommuneFragment on Commune {
    name
    code
    postalCode
}

fragment RNFFragment on RNF {
    id
    title
    address {
        ...AddressFragment
    }
}

fragment EngagementJuridiqueFragment on EngagementJuridique {
    montantEngage
    montantPaye
}
"""

# Pour les champs
CHAMP_FRAGMENTS = """
fragment RootChampFragment on Champ {
    ... on RepetitionChamp {
        rows {
            id
            champs {
                ...ChampFragment
                ... on CarteChamp {
                    geoAreas {
                        ...GeoAreaFragment
                    }
                }
                ... on DossierLinkChamp {
                    dossier {
                        id
                        number
                        state
                    }
                }
            }
        }
    }
    ... on CarteChamp {
        geoAreas {
            ...GeoAreaFragment
        }
    }
    ... on DossierLinkChamp {
        dossier {
            id
            number
            state
        }
    }
}

fragment ChampFragment on Champ {
    id
    champDescriptorId
    __typename
    label
    stringValue
    updatedAt
    prefilled
    ... on DateChamp {
        date
    }
    ... on DatetimeChamp {
        datetime
    }
    ... on CheckboxChamp {
        checked: value
    }
    ... on YesNoChamp {
        selected: value
    }
    ... on DecimalNumberChamp {
        decimalNumber: value
    }
    ... on IntegerNumberChamp {
        integerNumber: value
    }
    ... on CiviliteChamp {
        civilite: value
    }
    ... on LinkedDropDownListChamp {
        primaryValue
        secondaryValue
    }
    ... on MultipleDropDownListChamp {
        values
    }
    ... on PieceJustificativeChamp {
        files {
            ...FileFragment
        }
    }
    ... on AddressChamp {
        address {
            ...AddressFragment
        }
        commune {
            ...CommuneFragment
        }
        departement {
            ...DepartementFragment
        }
    }
    ... on EpciChamp {
        epci {
            ...EpciFragment
        }
        departement {
            ...DepartementFragment
        }
    }
    ... on CommuneChamp {
        commune {
            ...CommuneFragment
        }
        departement {
            ...DepartementFragment
        }
    }
    ... on DepartementChamp {
        departement {
            ...DepartementFragment
        }
    }
    ... on RegionChamp {
        region {
            ...RegionFragment
        }
    }
    ... on PaysChamp {
        pays {
            ...PaysFragment
        }
    }
    ... on SiretChamp {
        etablissement {
            ...PersonneMoraleFragment
        }
    }
    ... on RNFChamp {
        rnf {
            ...RNFFragment
        }
        commune {
            ...CommuneFragment
        }
        departement {
            ...DepartementFragment
        }
    }
    ... on EngagementJuridiqueChamp {
        engagementJuridique {
            ...EngagementJuridiqueFragment
        }
    }
}
"""

# Requête pour un dossier spécifique
query_get_dossier = """
query getDossier(
    $dossierNumber: Int!
    $includeChamps: Boolean = true
    $includeAnotations: Boolean = true
    $includeGeometry: Boolean = true
    $includeTraitements: Boolean = true
    $includeInstructeurs: Boolean = true
) {
    dossier(number: $dossierNumber) {
        ...DossierFragment
        demarche {
            ...DemarcheDescriptorFragment
        }
    }
}

fragment DemarcheDescriptorFragment on DemarcheDescriptor {
    id
    number
    title
    description
    state
    declarative
    dateCreation
    datePublication
    dateDerniereModification
    dateDepublication
    dateFermeture
}

fragment DossierFragment on Dossier {
    __typename
    id
    number
    archived
    prefilled
    state
    dateDerniereModification
    dateDepot
    datePassageEnConstruction
    datePassageEnInstruction
    dateTraitement
    dateExpiration
    dateSuppressionParUsager
    dateDerniereModificationChamps
    dateDerniereModificationAnnotations
    motivation
    usager {
        email
    }
    prenomMandataire
    nomMandataire
    deposeParUnTiers
    connectionUsager
    groupeInstructeur {
        id
        number
        label
    }
    demandeur {
        __typename
        ...PersonnePhysiqueFragment
        ...PersonneMoraleFragment
        ...PersonneMoraleIncompleteFragment
    }
    instructeurs @include(if: $includeInstructeurs) {
        id
        email
    }
    traitements @include(if: $includeTraitements) {
        state
        emailAgentTraitant
        dateTraitement
        motivation
    }
    champs @include(if: $includeChamps) {
        ...ChampFragment
        ...RootChampFragment
    }
    annotations @include(if: $includeAnotations) {
        ...ChampFragment
        ...RootChampFragment
    }
}

""" + COMMON_FRAGMENTS + SPECIALIZED_FRAGMENTS + CHAMP_FRAGMENTS

# Requête pour une démarche OPTIMISÉE avec filtres côté serveur
query_get_demarche = """
query getDemarche(
    $demarcheNumber: Int!
    $includeChamps: Boolean = true
    $includeAnotations: Boolean = true
    $includeRevision: Boolean = true
    $includeDossiers: Boolean = true
    $includeGeometry: Boolean = true
    $includeTraitements: Boolean = true
    $includeInstructeurs: Boolean = true
    $afterCursor: String = null
    $createdSince: ISO8601DateTime = null
    $createdUntil: ISO8601DateTime = null
    $instructeurs: [ID!] = null
    $states: [DossierState!] = null
) {
    demarche(number: $demarcheNumber) {
        id
        number
        title
        state
        declarative
        dateCreation
        dateFermeture
        activeRevision @include(if: $includeRevision) {
            ...RevisionFragment
        }
        dossiers(
            first: 100
            after: $afterCursor
            createdSince: $createdSince
            createdUntil: $createdUntil
            instructeurs: $instructeurs
            states: $states
        ) @include(if: $includeDossiers) {
            pageInfo {
                ...PageInfoFragment
            }
            nodes {
                ...DossierFragment
            }
        }
    }
}

fragment PageInfoFragment on PageInfo {
    hasPreviousPage
    hasNextPage
    startCursor
    endCursor
}

fragment RevisionFragment on Revision {
    id
    datePublication
    champDescriptors {
        ...ChampDescriptorFragment
        ... on RepetitionChampDescriptor {
            champDescriptors {
                ...ChampDescriptorFragment
            }
        }
    }
    annotationDescriptors {
        ...ChampDescriptorFragment
        ... on RepetitionChampDescriptor {
            champDescriptors {
                ...ChampDescriptorFragment
            }
        }
    }
}

fragment ChampDescriptorFragment on ChampDescriptor {
    __typename
    id
    label
    description
    required
    ... on DropDownListChampDescriptor {
        options
        otherOption
    }
    ... on MultipleDropDownListChampDescriptor {
        options
    }
    ... on LinkedDropDownListChampDescriptor {
        options
    }
    ... on PieceJustificativeChampDescriptor {
        fileTemplate {
            ...FileFragment
        }
    }
    ... on ExplicationChampDescriptor {
        collapsibleExplanationEnabled
        collapsibleExplanationText
    }
}

fragment DossierFragment on Dossier {
    __typename
    id
    number
    archived
    prefilled
    state
    dateDerniereModification
    dateDepot
    datePassageEnConstruction
    datePassageEnInstruction
    dateTraitement
    usager {
        email
    }
    groupeInstructeur {
        id
        number
        label
    }
    demandeur {
        __typename
        ...PersonnePhysiqueFragment
        ...PersonneMoraleFragment
        ...PersonneMoraleIncompleteFragment
    }
    instructeurs @include(if: $includeInstructeurs) {
        id
        email
    }
    traitements @include(if: $includeTraitements) {
        state
        emailAgentTraitant
        dateTraitement
        motivation
    }
    champs @include(if: $includeChamps) {
        ...ChampFragment
        ...RootChampFragment
    }
    annotations @include(if: $includeAnotations) {
        ...ChampFragment
        ...RootChampFragment
    }
    labels {
        id 
        name
        color
    }    
}

""" + COMMON_FRAGMENTS + SPECIALIZED_FRAGMENTS + CHAMP_FRAGMENTS

# Fonctions d'API
def get_dossier(dossier_number: int) -> Dict[str, Any]:
    """
    Récupère les détails d'un dossier avec tous ses champs.
    Filtre les champs HeaderSectionChamp et ExplicationChamp.
    Ignore les erreurs de permission.
    """
    if not API_TOKEN:
        raise ValueError("Le token d'API n'est pas configuré. Définissez DEMARCHES_API_TOKEN dans le fichier .env")
    
    # Variables pour la requête
    variables = {
        "dossierNumber": dossier_number,
        "includeChamps": True,
        "includeAnotations": True,
        "includeGeometry": True,
        "includeTraitements": True,
        "includeInstructeurs": True,
    }
    
    # En-têtes pour la requête
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Exécution de la requête
    response = requests.post(
        API_URL,
        json={"query": query_get_dossier, "variables": variables},
        headers=headers
    )
    
    # Vérification du code de statut
    response.raise_for_status()
    
    # Analyse de la réponse JSON
    result = response.json()
    
    # Vérifier les erreurs mais ne pas s'arrêter pour les erreurs de permission
    if "errors" in result:
        # Séparer les erreurs de permission des autres erreurs
        permission_errors = []
        other_errors = []
        
        for error in result["errors"]:
            error_message = error.get("message", "Unknown error")
            if "permissions" in error_message:
                permission_errors.append(error_message)
            else:
                other_errors.append(error_message)
        
        # Signaler les erreurs de permission mais continuer
        if permission_errors:
            print(f"Attention: Le dossier {dossier_number} a {len(permission_errors)} erreurs de permission")
        
        # S'arrêter uniquement pour les autres types d'erreurs
        if other_errors:
            raise Exception(f"GraphQL errors: {', '.join(other_errors)}")
    
    # Si les données sont nulles ou si le dossier est null à cause des permissions, retournez un dictionnaire vide
    if not result.get("data") or not result["data"].get("dossier"):
        print(f"Attention: Le dossier {dossier_number} n'est pas accessible ou n'existe pas")
        return {}
    
    dossier = result["data"]["dossier"]
    
    # Filtrer les champs indésirables
    filtered_dossier = dossier.copy()
    
    # Filtrer les champs
    if "champs" in filtered_dossier:
        filtered_dossier["champs"] = [
            champ for champ in filtered_dossier["champs"] 
            if champ.get("__typename") not in ["HeaderSectionChamp", "ExplicationChamp"]
        ]
    
    # Filtrer les annotations
    if "annotations" in filtered_dossier:
        filtered_dossier["annotations"] = [
            annotation for annotation in filtered_dossier["annotations"] 
            if annotation.get("__typename") not in ["HeaderSectionChamp", "ExplicationChamp"]
        ]
    
    return filtered_dossier

def get_demarche(demarche_number: int) -> Dict[str, Any]:
    """
    Récupère les détails d'une démarche avec tous ses dossiers accessibles.
    Ignore les erreurs de permission sur certains dossiers ou champs.
    """
    if not API_TOKEN:
        raise ValueError("Le token d'API n'est pas configuré. Définissez DEMARCHES_API_TOKEN dans le fichier .env")
    
    # Variables pour la requête
    variables = {
        "demarcheNumber": demarche_number,
        "includeChamps": True,
        "includeAnotations": True,
        "includeRevision": True,
        "includeDossiers": True,
        "includeGeometry": True,
        "includeTraitements": True,
        "includeInstructeurs": True,
    }
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        API_URL,
        json={"query": query_get_demarche, "variables": variables},
        headers=headers
    )
    
    response.raise_for_status()
    result = response.json()
    
    # Ignorer les erreurs spécifiques liées aux permissions
    if "errors" in result:
        # Filtrer les erreurs pour ne conserver que celles qui ne sont pas liées aux permissions
        filtered_errors = []
        permission_errors_count = 0
        
        for error in result["errors"]:
            error_message = error.get("message", "")
            if "permissions" in error_message or "hidden due to permissions" in error_message:
                permission_errors_count += 1
            else:
                filtered_errors.append(error_message)
        
        # Afficher le nombre d'erreurs de permission, mais continuer le traitement
        if permission_errors_count > 0:
            print(f"Attention: {permission_errors_count} objets masqués en raison de restrictions de permissions")
        
        # Ne lever une exception que pour les erreurs non liées aux permissions
        if filtered_errors:
            raise Exception(f"GraphQL errors: {', '.join(filtered_errors)}")
    
    # Si aucune donnée n'est retournée, c'est un problème
    if not result.get("data") or not result["data"].get("demarche"):
        raise Exception(f"Aucune donnée de démarche trouvée pour le numéro {demarche_number}")
    
    demarche = result["data"]["demarche"]
    
    # Filtrer les descripteurs de champs dans la révision active
    if "activeRevision" in demarche and demarche["activeRevision"]:
        active_revision = demarche["activeRevision"]
        
        # Filtrer les descripteurs de champs
        if "champDescriptors" in active_revision:
            active_revision["champDescriptors"] = [
                descriptor for descriptor in active_revision["champDescriptors"]
                if descriptor.get("type") not in ["HeaderSectionChamp", "ExplicationChamp"]
            ]
        
        # Filtrer les descripteurs d'annotations
        if "annotationDescriptors" in active_revision:
            active_revision["annotationDescriptors"] = [
                descriptor for descriptor in active_revision["annotationDescriptors"]
                if descriptor.get("type") not in ["HeaderSectionChamp", "ExplicationChamp"]
            ]
    
    # S'assurer que les structures de dossiers existent, même si vides
    if "dossiers" not in demarche:
        demarche["dossiers"] = {"nodes": []}
    elif not demarche["dossiers"] or "nodes" not in demarche["dossiers"]:
        demarche["dossiers"]["nodes"] = []
    
    # Filtrer les champs problématiques dans les dossiers
    for dossier in demarche["dossiers"]["nodes"]:
        # Filtrer les champs de chaque dossier
        if "champs" in dossier:
            dossier["champs"] = [
                champ for champ in dossier["champs"]
                if champ.get("__typename") not in ["HeaderSectionChamp", "ExplicationChamp"]
            ]
        
        # Filtrer les annotations de chaque dossier
        if "annotations" in dossier:
            dossier["annotations"] = [
                annotation for annotation in dossier["annotations"]
                if annotation.get("__typename") not in ["HeaderSectionChamp", "ExplicationChamp"]
            ]
    
    dossier_count = len(demarche["dossiers"]["nodes"])
    print(f"Démarche récupérée avec succès: {dossier_count} dossiers accessibles")
    
    return demarche

def get_demarche_dossiers_filtered(
    demarche_number: int, 
    date_debut: str = None, 
    date_fin: str = None,
    groupes_instructeurs: List[str] = None,
    statuts: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Récupère les dossiers avec filtrage côté serveur RÉEL.
    Utilise SEULEMENT les paramètres qui fonctionnent vraiment selon les tests.
    
    PARAMÈTRES RÉELLEMENT SUPPORTÉS :
    [OK]createdSince: ISO8601DateTime (date de début)
    ❌ createdUntil: Non supporté
    ❌ groupeInstructeurNumber: Non supporté  
    ❌ states: Non supporté
    
    Les autres filtres seront appliqués côté client sur le résultat réduit.
    """
    if not API_TOKEN:
        raise ValueError("Le token d'API n'est pas configuré.")
    
    # Seuls les filtres côté serveur qui fonctionnent
    server_filters = {}
    client_filters = {}
    
    # [OK]FILTRE CÔTÉ SERVEUR : Date de début seulement
    if date_debut:
        if 'T' not in date_debut:
            date_debut += 'T00:00:00Z'
        server_filters['createdSince'] = date_debut
        print(f"🗓️ Filtre serveur par date de début: {date_debut}")
    
    # ❌ FILTRES CÔTÉ CLIENT : Tout le reste
    if date_fin:
        client_filters['date_fin'] = date_fin
        print(f"🗓️ Filtre client par date de fin: {date_fin}")
    
    if groupes_instructeurs:
        client_filters['groupes_instructeurs'] = groupes_instructeurs
        print(f"👥 Filtre client par groupes: {groupes_instructeurs}")
    
    if statuts:
        client_filters['statuts'] = statuts
        print(f"📋 Filtre client par statuts: {statuts}")
    
    if server_filters:
        print(f"[FILTRAGE] Filtres côté serveur: {list(server_filters.keys())}")
    if client_filters:
        print(f"💻 Filtres côté client: {list(client_filters.keys())}")
    
    # Variables pour la requête (SIMPLIFIÉES)
    variables = {
        "demarcheNumber": demarche_number,
        "afterCursor": None,
        **server_filters  # Seulement createdSince
    }
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Requête GraphQL MINIMALISTE qui fonctionne
    query_get_demarche = """
    query getDemarche(
        $demarcheNumber: Int!
        $afterCursor: String = null
        $createdSince: ISO8601DateTime = null
    ) {
        demarche(number: $demarcheNumber) {
            id
            number
            title
            dossiers(
                first: 100
                after: $afterCursor
                createdSince: $createdSince
            ) {
                pageInfo {
                    hasPreviousPage
                    hasNextPage
                    startCursor
                    endCursor
                }
                nodes {
                    __typename
                    id
                    number
                    archived
                    prefilled
                    state
                    dateDerniereModification
                    dateDepot
                    datePassageEnConstruction
                    datePassageEnInstruction
                    dateTraitement
                    usager {
                        email
                    }
                    groupeInstructeur {
                        id
                        number
                        label
                    }
                    demandeur {
                        __typename
                        ... on PersonnePhysique {
                            civilite
                            nom
                            prenom
                            email
                        }
                        ... on PersonneMorale {
                            siret
                            siegeSocial
                            naf
                            libelleNaf
                            entreprise {
                                siren
                                raisonSociale
                                nomCommercial
                            }
                        }
                        ... on PersonneMoraleIncomplete {
                            siret
                        }
                    }
                    labels {
                        id 
                        name
                        color
                    }    
                }
            }
        }
    }
    """
    
    # Exécution de la requête
    print(f"[RECHERCHE] Exécution requête avec filtres serveur supportés...")
    
    response = requests.post(
        API_URL,
        json={"query": query_get_demarche, "variables": variables},
        headers=headers
    )
    
    response.raise_for_status()
    result = response.json()
    
    if "errors" in result:
        error_messages = [error.get("message", "Unknown error") for error in result["errors"]]
        print(f"❌ Erreurs GraphQL: {error_messages}")
        raise Exception(f"GraphQL errors: {', '.join(error_messages)}")
    
    # Récupération avec pagination
    demarche_data = result["data"]["demarche"]
    dossiers = []
    
    if "dossiers" in demarche_data and "nodes" in demarche_data["dossiers"]:
        dossiers = demarche_data["dossiers"]["nodes"]
        total_dossiers = len(dossiers)
        print(f"[OK]Première page récupérée: {total_dossiers} dossiers")
        
        # Pagination
        has_next_page = demarche_data["dossiers"]["pageInfo"]["hasNextPage"]
        cursor = demarche_data["dossiers"]["pageInfo"]["endCursor"]
        page_num = 1
        
        while has_next_page:
            page_num += 1
            print(f"📄 Page {page_num}...")
            
            variables["afterCursor"] = cursor
            
            next_response = requests.post(
                API_URL,
                json={"query": query_get_demarche, "variables": variables},
                headers=headers
            )
            
            next_response.raise_for_status()
            next_result = next_response.json()
            
            if "errors" in next_result:
                print(f"❌ Erreurs page {page_num}: {next_result['errors']}")
                break
            
            next_demarche = next_result["data"]["demarche"]
            
            if "dossiers" in next_demarche and "nodes" in next_demarche["dossiers"]:
                new_dossiers = next_demarche["dossiers"]["nodes"]
                dossiers.extend(new_dossiers)
                total_dossiers += len(new_dossiers)
                print(f"[OK]Page {page_num}: +{len(new_dossiers)} (total: {total_dossiers})")
                
                has_next_page = next_demarche["dossiers"]["pageInfo"]["hasNextPage"]
                cursor = next_demarche["dossiers"]["pageInfo"]["endCursor"]
            else:
                has_next_page = False
    
    print(f"[SUCCES] Récupération côté serveur: {len(dossiers)} dossiers")
    
    # ===========================================
    # FILTRAGE CÔTÉ CLIENT pour les autres critères
    # ===========================================
    
    if not client_filters:
        print(f"[OK]Aucun filtre côté client - résultat final: {len(dossiers)} dossiers")
        return dossiers
    
    print(f"[FILTRAGE] Application des filtres côté client...")
    dossiers_avant = len(dossiers)
    filtered_dossiers = []
    
    for dossier in dossiers:
        # Filtre par date de fin
        if client_filters.get('date_fin'):
            date_fin_str = client_filters['date_fin']
            if 'T' not in date_fin_str:
                date_fin_str += 'T23:59:59Z'
            
            try:
                from datetime import datetime
                date_depot = datetime.fromisoformat(dossier['dateDepot'].replace('Z', '+00:00'))
                date_limite_fin = datetime.fromisoformat(date_fin_str.replace('Z', '+00:00'))
                
                if date_depot > date_limite_fin:
                    continue
            except (ValueError, AttributeError, TypeError):
                continue
        
        # Filtre par groupe instructeur
        if client_filters.get('groupes_instructeurs'):
            groupes_cibles = client_filters['groupes_instructeurs']
            groupe_instructeur = dossier.get('groupeInstructeur')
            
            if not groupe_instructeur:
                continue
                
            groupe_number = str(groupe_instructeur.get('number', ''))
            groupe_id = groupe_instructeur.get('id', '')
            
            # Vérifier si le groupe correspond
            if not (groupe_number in groupes_cibles or groupe_id in groupes_cibles):
                continue
        
        # Filtre par statut
        if client_filters.get('statuts'):
            statuts_cibles = client_filters['statuts']
            if dossier.get('state') not in statuts_cibles:
                continue
        
        # Si tous les filtres passent, garder le dossier
        filtered_dossiers.append(dossier)
    
    print(f"[OK]Filtrage côté client terminé: {len(filtered_dossiers)}/{dossiers_avant} dossiers conservés")
    
    # Debug : Afficher quelques exemples
    if filtered_dossiers:
        print(f"📊 Exemples de résultats finaux:")
        for i, dossier in enumerate(filtered_dossiers[:3]):
            groupe = dossier.get('groupeInstructeur', {})
            print(f"   {i+1}. Dossier {dossier['number']}: {dossier['dateDepot'][:10]} - {dossier['state']}")
            print(f"      Groupe: {groupe.get('number')} ({groupe.get('label', 'Sans label')})")
    
    return filtered_dossiers


# ================================================
# SCRIPT DE TEST SIMPLE qui fonctionne
# ================================================

def test_working_filter():
    """
    Test avec SEULEMENT les paramètres qui fonctionnent
    """
    print("=== TEST avec seulement createdSince (qui fonctionne) ===")
    
    query = """
    query testWorkingFilter($demarcheNumber: Int!, $createdSince: ISO8601DateTime) {
        demarche(number: $demarcheNumber) {
            id
            title
            dossiers(first: 5, createdSince: $createdSince) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                nodes {
                    id
                    number
                    dateDepot
                    state
                    groupeInstructeur {
                        id
                        number
                        label
                    }
                }
            }
        }
    }
    """
    
    variables = {
        "demarcheNumber": 70018,
        "createdSince": "2025-06-15T00:00:00Z"
    }
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        API_URL,
        json={"query": query, "variables": variables},
        headers=headers
    )
    
    if response.status_code == 200:
        result = response.json()
        if "errors" in result:
            print(f"❌ Erreurs: {result['errors']}")
        else:
            dossiers = result["data"]["demarche"]["dossiers"]["nodes"]
            print(f"[OK]SUCCESS! {len(dossiers)} dossiers après 2025-06-15")
            
            for dossier in dossiers:
                groupe = dossier['groupeInstructeur']
                print(f"   📁 {dossier['number']}: {dossier['dateDepot'][:10]} - Groupe {groupe['number']}")
    else:
        print(f"❌ Erreur HTTP: {response.status_code}")


if __name__ == "__main__":
    test_working_filter()


# ================================================
# RÉCAPITULATIF des paramètres API réels
# ================================================

"""
[FILTRAGE] PARAMÈTRES GRAPHQL RÉELLEMENT SUPPORTÉS (testé) :

[OK]CÔTÉ SERVEUR :
- createdSince: ISO8601DateTime  # Date de début uniquement

❌ NON SUPPORTÉS côté serveur :
- createdUntil                   # Date de fin  
- groupeInstructeurNumber        # Groupe instructeur
- states                         # Statuts des dossiers

💻 SOLUTION HYBRIDE :
1. Filtrer par date de début côté serveur (gain majeur)
2. Filtrer le reste côté client sur le résultat réduit

🎯 PERFORMANCE :
Au lieu de récupérer 6450 dossiers puis tout filtrer,
on récupère ~200 dossiers (après 2025-06-15) puis on filtre 
seulement ceux-là par groupe et statut.

GAIN ESTIMÉ : 30x plus rapide !
"""

def get_demarche_dossiers(demarche_number: int):
    """
    Récupère uniquement la liste des dossiers d'une démarche, avec gestion de la pagination.
    Récupère tous les dossiers même s'il y en a plus de 100.
    ANCIENNE VERSION - utilisez get_demarche_dossiers_filtered pour de meilleures performances.
    """
    return get_demarche_dossiers_filtered(demarche_number)

def get_dossier_geojson(dossier_number: int) -> Dict[str, Any]:
    """
    Récupère les données géométriques d'un dossier au format GeoJSON.
    """
    if not API_TOKEN:
        raise ValueError("Le token d'API n'est pas configuré. Définissez DEMARCHES_API_TOKEN dans le fichier .env")
    
    base_url = API_URL.split('/api/')[0] if '/api/' in API_URL else "https://www.demarches-simplifiees.fr"
    url = f"{base_url}/dossiers/{dossier_number}/geojson"
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Accept": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    return response.json()