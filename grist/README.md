# grist

Ce dossier contient les responsabilités strictement limitées à Grist.

## Responsabilités

- Dialoguer avec l'API Grist (lecture, écriture, gestion des erreurs).
- Appliquer les règles propres à Grist, dont la construction des identifiants
  de tables et de colonnes à partir des libellés Démarche Numérique : cette
  règle est unique et partagée par tous les modules (schéma, extraction,
  blocs répétables). Une seconde implémentation fait diverger les noms, et les
  valeurs ne trouvent plus leur colonne.
