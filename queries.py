import os
import traceback
from pprint import pprint
from dotenv import load_dotenv

# Import des modules locaux
from queries_config import API_TOKEN
from queries_graphql import get_dossier, get_demarche, get_demarche_dossiers, get_dossier_geojson
from queries_util import format_complex_json_for_grist, associate_geojson_with_champs
from queries_extract import extract_champ_values, dossier_to_flat_data

# Exposer les fonctions principales pour l'importation dans d'autres scripts
__all__ = [
    'get_dossier', 
    'get_demarche', 
    'get_demarche_dossiers', 
    'get_dossier_geojson',
    'extract_champ_values', 
    'dossier_to_flat_data', 
    'associate_geojson_with_champs',
    'format_complex_json_for_grist'
]

# Code d'exemple pour tester le script
if __name__ == "__main__":
    try:
        # Charger les variables d'environnement
        load_dotenv()
        
        # Récupérer le numéro de démarche depuis le fichier .env
        demarche_number = os.getenv("DEMARCHE_NUMBER")
        if demarche_number:
            demarche_number = int(demarche_number)
            print(f"Récupération de la démarche {demarche_number}...")
            
            # Récupérer la démarche
            demarche_data = get_demarche(demarche_number)
            
            print("\nInformations de la démarche:")
            print(f"Titre: {demarche_data['title']}")
            print(f"État: {demarche_data['state']}")
            
            # Vérifier si des dossiers ont été récupérés
            dossiers = []
            if 'dossiers' in demarche_data and 'nodes' in demarche_data['dossiers']:
                dossiers = demarche_data['dossiers']['nodes']
            
            print(f"Nombre de dossiers récupérés: {len(dossiers)}")
            
            # Si des dossiers ont été trouvés, afficher le détail du premier
            if dossiers:
                dossier = dossiers[0]  # Prendre le premier dossier pour l'exemple
                dossier_number = dossier["number"]
                print(f"\nAffichage détaillé du dossier {dossier_number}:")
                
                # Récupérer toutes les données du dossier
                detailed_dossier = get_dossier(dossier_number)
                
                # Transformer les données du dossier
                flat_data = dossier_to_flat_data(detailed_dossier)
                
                # Afficher les différentes sections
                print("\n--- Informations du dossier ---")
                pprint(flat_data["dossier"])
                
                print("\n--- Champs ---")
                for champ in flat_data["champs"][:10]:  # Limiter à 10 pour la lisibilité
                    pprint(champ)
                
                print("\n--- Blocs répétables ---")
                for row in flat_data["repetable_rows"][:5]:  # Limiter à 5 pour la lisibilité
                    pprint(row)
                
                # Option : exporter vers un fichier JSON si souhaité
                import json
                with open(f"dossier_{dossier_number}_flat_data.json", "w", encoding="utf-8") as f:
                    json.dump(flat_data, f, ensure_ascii=False, indent=2)
                print(f"\nDonnées exportées dans dossier_{dossier_number}_flat_data.json")
            
        else:
            print("Aucun numéro de démarche trouvé dans le fichier .env. Veuillez définir DEMARCHE_NUMBER.")
        
    except Exception as e:
        print(f"Erreur: {e}")
        # Afficher la trace complète pour le débogage
        traceback.print_exc()