from queries_graphql import get_session_with_retries
from utils.constants import DEMARCHES_API_URL


def get_groups(api_token: str, demarche_number: int) -> list[tuple[int, str]]:
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
            return []

        groupes = (
            result.get("data", {}).get("demarche", {}).get("groupeInstructeurs", [])
        )
        return [(groupe.get("number"), groupe.get("label")) for groupe in groupes]

    except Exception:
        return []
