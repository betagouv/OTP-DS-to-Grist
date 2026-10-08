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

# Liste blanche des instances Grist joignables, séparée par des virgules :
# domaines seuls (le schéma, le port et le chemin sont ignorés), un joker
# `*.suffixe` couvre tous les sous-domaines de `suffixe`. La variable est
# requise : sans elle, aucune instance ne serait autorisée et l'application
# refuserait toute synchronisation. La valeur reste brute ici, elle est analysée
# par `grist/base_url.py` au chargement du module.
GRIST_BASE_URL_WHITELIST: str = os.getenv("GRIST_BASE_URL_WHITELIST", "")
if not GRIST_BASE_URL_WHITELIST:
    raise ValueError(
        "GRIST_BASE_URL_WHITELIST environment variable is required "
        "(comma-separated list of allowed Grist domains)"
    )

CHANGELOG_PATH: str = os.path.join(os.path.dirname(__file__), "CHANGELOG.md")
GITHUB_CHANGELOG_BASE_URL: str = "https://github.com/betagouv/OTP-DS-to-Grist/blob/main/CHANGELOG.md"

EXIT_CODE_EXTERNAL_API_ERROR: int = 2

# Lecture d'une table Grist en échec (GristReadError) : erreur transitoire,
# la synchro planifiée n'est pas désactivée et reprendra au prochain run.
EXIT_CODE_GRIST_READ_ERROR: int = 3

# Durée de validité du cache des bannissements d'IP, en secondes.
IP_BLOCKLIST_CACHE_TTL_SECONDS: float = float(
    os.getenv("IP_BLOCKLIST_CACHE_TTL_SECONDS", "60")
)

# Nombre de 404 par IP, sur la fenêtre glissante, au-delà duquel l'IP est bannie.
IP_BLOCKLIST_THRESHOLD: int = int(os.getenv("IP_BLOCKLIST_THRESHOLD", "3"))

# Longueur de la fenêtre glissante de comptage des 404, en secondes.
IP_BLOCKLIST_WINDOW_SECONDS: float = float(
    os.getenv("IP_BLOCKLIST_WINDOW_SECONDS", "10")
)

# Liste blanche d'IP, séparée par des virgules : IP seules ou CIDR. Une
# variable non renseignée donne une liste blanche vide, ce qui est valide. La
# valeur reste brute ici, elle est analysée par `parse_whitelist` à
# l'initialisation de l'application.
IP_BLOCKLIST_WHITELIST: str = os.getenv("IP_BLOCKLIST_WHITELIST", "")

HELP_LINK_FAQ: str = os.getenv("HELP_LINK_FAQ", "")
if not HELP_LINK_FAQ:
    raise ValueError("HELP_LINK_FAQ environment variable is required")

HELP_LINK_DN_TOKEN_API: str = os.getenv("HELP_LINK_DN_TOKEN_API", "")
if not HELP_LINK_DN_TOKEN_API:
    raise ValueError("HELP_LINK_DN_TOKEN_API environment variable is required")

HELP_LINK_GRIST_API_KEY: str = os.getenv("HELP_LINK_GRIST_API_KEY", "")
if not HELP_LINK_GRIST_API_KEY:
    raise ValueError("HELP_LINK_GRIST_API_KEY environment variable is required")
