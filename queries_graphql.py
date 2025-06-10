import requests
import json
from typing import Dict, Any
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

# Requête pour une démarche
# Requête pour une démarche
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

def get_demarche_dossiers(demarche_number: int):
    """
    Récupère uniquement la liste des dossiers d'une démarche, avec gestion de la pagination.
    Récupère tous les dossiers même s'il y en a plus de 100.
    """
    if not API_TOKEN:
        raise ValueError("Le token d'API n'est pas configuré. Définissez DEMARCHES_API_TOKEN dans le fichier .env")
    
    # Variables pour la requête avec inclusion minimale
    variables = {
        "demarcheNumber": demarche_number,
        "includeChamps": False,
        "includeAnotations": False,
        "includeRevision": False,
        "includeDossiers": True,
        "includeGeometry": False,
        "includeTraitements": False,
        "includeInstructeurs": False,
        "afterCursor": None
    }
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Première requête pour récupérer la première page
    response = requests.post(
        API_URL,
        json={"query": query_get_demarche, "variables": variables},
        headers=headers
    )
    
    response.raise_for_status()
    result = response.json()
    
    if "errors" in result:
        error_messages = [error.get("message", "Unknown error") for error in result["errors"]]
        raise Exception(f"GraphQL errors: {', '.join(error_messages)}")
    
    # Récupérer les dossiers initiaux
    demarche_data = result["data"]["demarche"]
    dossiers = []
    
    if "dossiers" in demarche_data and "nodes" in demarche_data["dossiers"]:
        dossiers = demarche_data["dossiers"]["nodes"]
        total_dossiers = len(dossiers)
        print(f"Première page récupérée: {total_dossiers} dossiers")
        
        # Récupérer les pages suivantes tant qu'il y en a
        has_next_page = demarche_data["dossiers"]["pageInfo"]["hasNextPage"]
        cursor = demarche_data["dossiers"]["pageInfo"]["endCursor"]
        page_num = 1
        
        while has_next_page:
            page_num += 1
            print(f"Récupération de la page {page_num} des dossiers après le curseur: {cursor}")
            
            # Mettre à jour le curseur pour la page suivante
            variables["afterCursor"] = cursor
            
            # Requête pour la page suivante
            next_response = requests.post(
                API_URL,
                json={"query": query_get_demarche, "variables": variables},
                headers=headers
            )
            
            next_response.raise_for_status()
            next_result = next_response.json()
            
            if "errors" in next_result:
                error_messages = [error.get("message", "Unknown error") for error in next_result["errors"]]
                raise Exception(f"GraphQL errors: {', '.join(error_messages)}")
            
            next_demarche = next_result["data"]["demarche"]
            
            # Ajouter les dossiers de la nouvelle page
            if "dossiers" in next_demarche and "nodes" in next_demarche["dossiers"]:
                new_dossiers = next_demarche["dossiers"]["nodes"]
                dossiers.extend(new_dossiers)
                total_dossiers += len(new_dossiers)
                print(f"Page {page_num} récupérée: {len(new_dossiers)} dossiers (total: {total_dossiers})")
                
                # Mettre à jour les informations de pagination
                has_next_page = next_demarche["dossiers"]["pageInfo"]["hasNextPage"]
                cursor = next_demarche["dossiers"]["pageInfo"]["endCursor"]
            else:
                has_next_page = False
    
    print(f"Récupération complète: {len(dossiers)} dossiers pour la démarche {demarche_number}")
    return dossiers

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