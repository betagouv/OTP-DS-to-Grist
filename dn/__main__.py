"""
Script CLI pour tester la connexion à l'API Démarche Numérique
et récupérer des données d'une démarche.

Usage:
    python -m dn
"""

import os
import json
import traceback
from pprint import pprint

from dotenv import load_dotenv

from dn.queries import get_dossier, get_demarche
from dn.extract import dossier_to_flat_data
from utils.api_validator import test_demarches_api


if __name__ == "__main__":
    try:
        load_dotenv()

        api_token = os.getenv("DEMARCHES_API_TOKEN")
        demarche_number = os.getenv("DEMARCHE_NUMBER")

        if not api_token:
            print("Token API non défini, impossible de tester la connexion")
            exit(1)

        print("Vérification de la connexion à l'API Démarche Numérique")
        success, message, _ = test_demarches_api(api_token, demarche_number)

        if not success:
            print(f"Échec de la connexion: {message}")
            exit(1)

        print(f"{message}")

        if not demarche_number:
            print(
                "Aucun numéro de démarché trouvé dans le fichier .env. "
                "Veuillez définir DEMARCHE_NUMBER."
            )
            exit(1)

        demarche_number = int(demarche_number)
        print(f"Récupération de la démarche {demarche_number}...")

        demarche_data = get_demarche(demarche_number)

        print("\nInformations de la démarche:")
        print(f"Titre: {demarche_data['title']}")
        print(f"État: {demarche_data['state']}")

        dossiers = []
        if "dossiers" in demarche_data and "nodes" in demarche_data["dossiers"]:
            dossiers = demarche_data["dossiers"]["nodes"]

        print(f"Nombre de dossiers récupérés: {len(dossiers)}")

        if dossiers:
            dossier = dossiers[0]
            dossier_number = dossier["number"]
            print(f"\nAffichage détaillé du dossier {dossier_number}:")

            detailed_dossier = get_dossier(dossier_number)
            flat_data = dossier_to_flat_data(detailed_dossier)

            print("\n--- Informations du dossier ---")
            pprint(flat_data["dossier"])

            print("\n--- Champs ---")
            for champ in flat_data["champs"][:10]:
                pprint(champ)

            print("\n--- Blocs répétables ---")
            for row in flat_data["repetable_rows"][:5]:
                pprint(row)

            with open(
                f"dossier_{dossier_number}_flat_data.json", "w", encoding="utf-8"
            ) as f:
                json.dump(flat_data, f, ensure_ascii=False, indent=2)
            print(
                f"\nDonnées exportées dans dossier_{dossier_number}_flat_data.json"
            )

    except Exception as e:
        print(f"Erreur: {e}")
        traceback.print_exc()
