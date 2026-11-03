# Outils d'exploitation

Ce dossier regroupe des outils en ligne de commande, lancés en local, pour observer
et dépanner les instances déployées (production, test). Ils ne font pas partie de
l'application : `app.py` ne les charge jamais.

## Instances Scalingo

Une instance est désignée par un nom court (`prod`, `test`…). Son application et sa
région Scalingo viennent de l'environnement (`.env`, non versionné), jamais du code
ni de la documentation :

```
SCALINGO_<INSTANCE>_APP=<nom de l'application Scalingo>
SCALINGO_<INSTANCE>_REGION=<région, vide pour la région par défaut de la CLI>
```

Ajouter une instance revient à ajouter ces deux variables. L'agent opencode `@logs`
s'appuie sur la même convention.
