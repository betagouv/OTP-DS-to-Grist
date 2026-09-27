import os
from collections.abc import Iterator
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv

from utils.constants import DEMARCHES_API_URL
from utils.log import log, log_error
from utils.rate_limited_session import RateLimitedSession, build_rate_limited_session

load_dotenv()
API_TOKEN = os.getenv("DEMARCHES_API_TOKEN") or ""

PAGE_SIZE_DOSSIERS_MAX = 100

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

        capitalSocial
        codeEffectifEntreprise
        formeJuridique
        formeJuridiqueCode
        numeroTvaIntracommunautaire
        dateCreation
        etatAdministratif
    }

    association {
        rna
        titre
        objet
        dateCreation
        dateDeclaration
        datePublication
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
    streetNumber
    streetName
    postalCode
    cityName
    cityCode
    departmentName
    departmentCode
    regionName
    regionCode
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
        columns {
            __typename
            id
            label
            ... on TextColumn {
                value
            }
            ... on AttachmentsColumn {
                value {
                    ...FileFragment
                }
            }
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

PAGE_INFO_FRAGMENT = """
fragment PageInfoFragment on PageInfo {
    hasPreviousPage
    hasNextPage
    startCursor
    endCursor
}
"""

# Fragment dossier détaillé, partagé par la requête unitaire et la requête paginée
# (utilise les variables $include* que chaque requête doit déclarer)
DOSSIER_FRAGMENT = """
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
    dateDerniereCorrectionEnAttente @include(if: $includeCorrections)
    dateDerniereModificationChamps
    dateAccuseLectureAgreement
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
        event
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
    avis @include(if: $includeAvis) {
        id
        question
        reponse
        dateQuestion
        dateReponse
        claimant {
            email
        }
        expert {
            email
        }
    }
}
"""

# Requête paginée des dossiers DÉTAILLÉS d'une démarche
# (une page = la connexion `dossiers` complète, avec champs, annotations, avis…)
query_dossiers_detaille = (
    """
query getDossiersPage(
    $demarcheNumber: Int!
    $first: Int!
    $afterCursor: String = null
    $updatedSince: ISO8601DateTime = null
    $includeChamps: Boolean = true
    $includeAnotations: Boolean = true
    $includeGeometry: Boolean = true
    $includeTraitements: Boolean = true
    $includeInstructeurs: Boolean = true
    $includeAvis: Boolean = true
    $includeCorrections: Boolean = true
) {
    demarche(number: $demarcheNumber) {
        dossiers(
            first: $first
            after: $afterCursor
            updatedSince: $updatedSince
        ) {
            pageInfo {
                ...PageInfoFragment
            }
            nodes {
                ...DossierFragment
            }
        }
    }
}

"""
    + DOSSIER_FRAGMENT
    + PAGE_INFO_FRAGMENT
    + COMMON_FRAGMENTS
    + SPECIALIZED_FRAGMENTS
    + CHAMP_FRAGMENTS
)

# Requête pour un dossier spécifique
# Requête pour une démarche OPTIMISÉE avec filtres côté serveur
# SESSION GLOBALE (créée une seule fois)
_session: RateLimitedSession | None = None

# Configuration du rate limiting réactif des appels à l'API Démarches Numériques,
# surchargeable via variables d'environnement.
# Le retry 429 est assuré par utils.rate_limited_session.RateLimitedSession ;
# les constantes ci-dessous lui sont injectées à la création de la session.
#
# En-têtes d'une réponse 429 de l'API DN (voir rack_attack.rb côté DN) :
#   Retry-After        : secondes à attendre avant de relancer
#   RateLimit-Reset    : timestamp epoch (s) de fin de fenêtre (le plus fiable)
#   RateLimit-Remaining: vaut "0" sur un 429
#   RateLimit-Limit    : non transmis par l'API
DEMARCHES_MAX_429_RETRIES = max(1, int(os.getenv("DEMARCHES_MAX_429_RETRIES", "3")))
DEMARCHES_FALLBACK_429_DELAY = int(os.getenv("DEMARCHES_FALLBACK_429_DELAY", "60"))
DEMARCHES_MAX_RANDOM_DELAY_SECONDS = int(
    os.getenv("DEMARCHES_MAX_RANDOM_DELAY_SECONDS", "5")
)


def get_session_with_retries() -> RateLimitedSession:
    """
    Retourne une session HTTP avec retry (singleton).
    La session est créée une seule fois et réutilisée.
    """
    global _session

    if _session is None:
        _session = build_rate_limited_session(
            max_retries=DEMARCHES_MAX_429_RETRIES,
            fallback_delay=DEMARCHES_FALLBACK_429_DELAY,
            max_random_delay=DEMARCHES_MAX_RANDOM_DELAY_SECONDS,
        )

    return _session


# Champs d'affichage uniquement : sans valeur métier, ils ne doivent pas
# produire de colonnes dans Grist
DISPLAY_CHAMP_TYPES = ("HeaderSectionChamp", "ExplicationChamp")


def _strip_display_champs(dossier: dict[str, Any]) -> dict[str, Any]:
    """Retire des `champs` et des `annotations` les éléments purement d'affichage."""
    filtered = dossier.copy()
    for collection in ("champs", "annotations"):
        if collection in filtered:
            filtered[collection] = [
                element
                for element in filtered[collection]
                if element.get("__typename") not in DISPLAY_CHAMP_TYPES
            ]

    return filtered


# Fonctions d'API
def _dossier_nodes(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Dossiers d'une page paginée (liste vide si la démarche est inaccessible)."""
    return (data.get("demarche") or {}).get("dossiers", {}).get("nodes") or []


def _page_info(data: dict[str, Any]) -> tuple[bool, str | None]:
    """(hasNextPage, endCursor) d'une page paginée (démarche inaccessible = fin)."""
    page_info = (data.get("demarche") or {}).get("dossiers", {}).get("pageInfo")
    if not page_info:
        return False, None
    return bool(page_info["hasNextPage"]), page_info["endCursor"]


def iter_demarche_dossier_pages(
    demarche_number: int,
    session: requests.Session | None = None,
    page_size: int = PAGE_SIZE_DOSSIERS_MAX,
    updated_since: str | None = None,
) -> Iterator[list[dict[str, Any]]]:
    """
    Parcourt les dossiers d'une démarche PAGE PAR PAGE, en renvoyant des dossiers
    DÉTAILLÉS (champs, annotations, avis, traitements, géométrie des pièces jointes).

    Chaque page est rendue dès sa réception : le consommateur peut l'écrire (Grist)
    avant que la suivante soit demandée, et la mémoire reste bornée à une page,
    quel que soit le nombre de dossiers de la démarche.

    Yield:
        list[dict[str, Any]]: une page de dossiers, filtrés des champs
        d'affichage (en-têtes de section, explications).
    """
    if not API_TOKEN:
        raise ValueError("Le token d'API n'est pas configuré.")

    page_size = min(page_size, PAGE_SIZE_DOSSIERS_MAX)

    if session is None:
        session = get_session_with_retries()

    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
    }

    variables = {
        "demarcheNumber": demarche_number,
        "first": page_size,
        "updatedSince": updated_since,
        "includeChamps": True,
        "includeAnotations": True,
        "includeGeometry": True,
        "includeTraitements": True,
        "includeInstructeurs": True,
        "includeAvis": True,
        "includeCorrections": True,
    }

    page_num = 0
    has_next_page = True
    cursor = None
    while has_next_page:
        page_num += 1
        response = session.post(
            DEMARCHES_API_URL,
            json={
                "query": query_dossiers_detaille,
                "variables": {**variables, "afterCursor": cursor},
            },
            headers=headers,
        )
        response.raise_for_status()
        result = response.json()

        # Les dossiers en accès refusé n'apparaissent pas dans la page : on ignore
        # l'erreur et on poursuit, les autres dossiers restant exploitables.
        # Le message de l'API nomme le dossier masqué, on le restitue tel quel.
        if "errors" in result:
            messages = [e.get("message", "") for e in result["errors"]]
            if any("permissions" not in message for message in messages):
                raise Exception(f"GraphQL errors: {', '.join(messages)}")
            log(
                f"[DOSSIERS] {len(messages)} dossier(s) masqué(s) par les "
                f"permissions : {', '.join(messages)}"
            )

        data = result.get("data") or {}
        has_next_page, cursor_suivant = _page_info(data)
        page = [_strip_display_champs(node) for node in _dossier_nodes(data)]

        if page:
            log(f"[DOSSIERS] Page {page_num} : {len(page)} dossier(s) reçu(s)")
            yield page

        if not has_next_page:
            return

        # Un curseur qui n'avance pas ferait boucler sur la même page
        if cursor_suivant == cursor:
            log_error(
                f"[DOSSIERS] Curseur inchangé après la page {page_num} "
                "(démarche inexistante ou dossiers tous inaccessibles) : arrêt"
            )
            return
        cursor = cursor_suivant


def get_demarche_dossiers_labels_only(demarche_number: int) -> List[Dict[str, Any]]:
    """
    Récupère uniquement le numéro et les labels de TOUS les dossiers d'une démarche.

    Requête volontairement minimaliste (number + labels) : elle sert au rafraîchissement
    des labels, car l'ajout ou le retrait d'un label ne met pas à jour
    `dateDerniereModification` et échappe donc au filtre `updatedSince`.

    Returns:
        list[dict]: [{"number": int, "labels": [{"id", "name", "color"}, ...]}, ...]
    """
    if not API_TOKEN:
        raise ValueError("Le token d'API n'est pas configuré.")

    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
    }
    session = get_session_with_retries()

    query = """
    query getDemarcheLabels($demarcheNumber: Int!, $after: String) {
        demarche(number: $demarcheNumber) {
            dossiers(first: 100, after: $after) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                nodes {
                    number
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

    dossiers = []
    cursor = None
    page_num = 0
    has_next_page = True

    while has_next_page:
        page_num += 1
        response = session.post(
            DEMARCHES_API_URL,
            json={
                "query": query,
                "variables": {"demarcheNumber": demarche_number, "after": cursor},
            },
            headers=headers,
        )
        response.raise_for_status()
        result = response.json()

        if "errors" in result:
            messages = [e.get("message", "Unknown error") for e in result["errors"]]
            raise Exception(f"GraphQL errors: {', '.join(messages)}")

        connection = result["data"]["demarche"]["dossiers"]
        dossiers.extend(connection["nodes"])
        has_next_page = connection["pageInfo"]["hasNextPage"]
        cursor = connection["pageInfo"]["endCursor"]

    print(f"[LABELS] {len(dossiers)} dossiers récupérés en {page_num} page(s)")

    return dossiers


def get_deleted_dossiers(
    demarche_number: int, deleted_since: str = None
) -> List[Dict[str, Any]]:
    """
    Récupère les dossiers supprimés d'une démarche, en fusionnant :
    - deletedDossiers : suppression confirmée par DN
    - pendingDeletedDossiers : suppression en attente (période de grâce), mais déjà
    invisible pour les instructeurs dans DN — traité ici comme supprimé.
    Pagination complète sur les deux connexions.
    deleted_since (ISO8601) limite deletedDossiers aux suppressions récentes.
    """
    if not API_TOKEN:
        raise ValueError("Le token d'API n'est pas configuré.")

    if not deleted_since:
        deleted_since = None

    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
    }
    session = get_session_with_retries()
    all_deleted = []

    # --- deletedDossiers (suppression confirmée) ---
    query_deleted = """
    query getDeletedDossiers($demarcheNumber: Int!, $first: Int, $after: String, $since: ISO8601DateTime) {
        demarche(number: $demarcheNumber) {
            deletedDossiers(first: $first, after: $after, deletedSince: $since) {
                pageInfo { hasNextPage endCursor }
                nodes { number dateSupression state reason }
            }
        }
    }
    """
    cursor = None
    has_next_page = True
    while has_next_page:
        variables = {
            "demarcheNumber": demarche_number,
            "first": 100,
            "after": cursor,
            "since": deleted_since,
        }
        response = session.post(
            DEMARCHES_API_URL,
            json={"query": query_deleted, "variables": variables},
            headers=headers,
        )
        response.raise_for_status()
        result = response.json()
        if "errors" in result:
            messages = [e.get("message", "Unknown error") for e in result["errors"]]
            raise Exception(f"GraphQL errors: {', '.join(messages)}")
        connection = result["data"]["demarche"]["deletedDossiers"]
        all_deleted.extend(connection["nodes"])
        has_next_page = connection["pageInfo"]["hasNextPage"]
        cursor = connection["pageInfo"]["endCursor"]

    # --- pendingDeletedDossiers (en attente, mais déjà invisible pour les instructeurs) ---
    query_pending = """
    query getPendingDeletedDossiers($demarcheNumber: Int!, $first: Int, $after: String) {
        demarche(number: $demarcheNumber) {
            pendingDeletedDossiers(first: $first, after: $after) {
                pageInfo { hasNextPage endCursor }
                nodes { number dateSupression state reason }
            }
        }
    }
    """
    cursor = None
    has_next_page = True
    while has_next_page:
        variables = {"demarcheNumber": demarche_number, "first": 100, "after": cursor}
        response = session.post(
            DEMARCHES_API_URL,
            json={"query": query_pending, "variables": variables},
            headers=headers,
        )
        response.raise_for_status()
        result = response.json()
        if "errors" in result:
            messages = [e.get("message", "Unknown error") for e in result["errors"]]
            raise Exception(f"GraphQL errors: {', '.join(messages)}")
        connection = result["data"]["demarche"]["pendingDeletedDossiers"]
        all_deleted.extend(connection["nodes"])
        has_next_page = connection["pageInfo"]["hasNextPage"]
        cursor = connection["pageInfo"]["endCursor"]

    return all_deleted


def get_groups(
    api_token: str | None, demarche_number: str | None
) -> list[tuple[int, str]]:
    """Récupère les groupes instructeurs disponibles pour une démarche"""
    if not all([api_token, demarche_number]):
        return []

    try:
        query = """
        query getDemarche($demarcheNumber: Int!) {
            demarche(number: $demarcheNumber) {
                groupeInstructeurs {
                    id
                    number
                    label
                }
            }
        }
        """

        variables = {"demarcheNumber": int(demarche_number)}
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

        session = get_session_with_retries()
        response = session.post(
            DEMARCHES_API_URL,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=10,
        )

        if response.status_code != 200:
            return []

        result = response.json()
        if "errors" in result:
            messages = [e.get("message", "Unknown error") for e in result["errors"]]
            log_error(
                "Erreur GraphQL lors de la récupération des groupes instructeurs: "
                + ", ".join(messages)
            )
            return []

        groupes = (
            result.get("data", {}).get("demarche", {}).get("groupeInstructeurs", [])
        )
        return [(groupe.get("number"), groupe.get("label")) for groupe in groupes]

    except Exception as e:
        log_error(f"Erreur lors de la récupération des groupes instructeurs: {e}")
        return []
