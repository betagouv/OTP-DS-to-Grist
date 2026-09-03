import os
from dotenv import load_dotenv

load_dotenv()

# Constantes partagées pour toute l'application

DATABASE_URL: str = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is required for database operations"
    )

DEMARCHES_API_URL: str = "https://www.demarches-simplifiees.fr/api/v2/graphql"

CHANGELOG_PATH: str = os.path.join(os.path.dirname(__file__), "CHANGELOG.md")
GITHUB_CHANGELOG_BASE_URL: str = "https://github.com/betagouv/OTP-DS-to-Grist/blob/main/CHANGELOG.md"

EXIT_CODE_EXTERNAL_API_ERROR: int = 2

HELP_LINK_FAQ: str = os.getenv("HELP_LINK_FAQ", "")
if not HELP_LINK_FAQ:
    raise ValueError("HELP_LINK_FAQ environment variable is required")

HELP_LINK_DN_TOKEN_API: str = os.getenv("HELP_LINK_DN_TOKEN_API", "")
if not HELP_LINK_DN_TOKEN_API:
    raise ValueError("HELP_LINK_DN_TOKEN_API environment variable is required")

HELP_LINK_GRIST_API_KEY: str = os.getenv("HELP_LINK_GRIST_API_KEY", "")
if not HELP_LINK_GRIST_API_KEY:
    raise ValueError("HELP_LINK_GRIST_API_KEY environment variable is required")
