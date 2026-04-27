import os

# Constantes partagées pour toute l'application
DEMARCHES_API_URL: str = "https://www.demarches-simplifiees.fr/api/v2/graphql"

CHANGELOG_PATH: str = os.path.join(os.path.dirname(__file__), "CHANGELOG.md")
GITHUB_CHANGELOG_BASE_URL: str = "https://github.com/betagouv/OTP-DS-to-Grist/blob/main/CHANGELOG.md"

EXIT_CODE_EXTERNAL_API_ERROR: int = 2
