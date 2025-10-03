import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Récupérer le token depuis les variables d'environnement
API_TOKEN = os.getenv("DEMARCHES_API_TOKEN")
API_URL = os.getenv("DEMARCHES_API_URL", "https://www.demarches-simplifiees.fr/api/v2/graphql")