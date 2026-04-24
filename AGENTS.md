# AGENTS.md - Guide pour les agents de développement

Ce fichier contient les directives pour les agents IA travaillant sur ce projet.

## Préférences utilisateur

- Lancer les tests associés après chaque modification
- Demander des clarifications pour toute ambiguïté
- En cas de demande impliquant beaucoup de modifications, proposer un plan en étapes.
  - Pendant la conception du plan, analyser les risques de régressions
  - Ces étapes devraient être testables
  - Ces étapes ne doivent pas contenir régression
  - Ces étapes devraient être autonome et ne pas dépendre d'une prochaine étape dans la mesure du possible

## Contexte du projet

Ce projet a été initialement créé par un non-développeur avec assistance IA.

Il en résulte un code à remanier et des opportunités de refactoring régulières.

**Merci de :**
- Proposer des remaniements (refactoring) quand une opportunité est identifiée
- Simplifier le code quand une meilleure approche est trouvée
- Ne pas hésiter à réorganiser les fichiers si ça améliore la structure et regroupe des responsabilités
- Vérifier si une responsabilité est déjà existante et l'utiliser ou la faire évoluer

## Instructions pendant l'exploration

Lire le fichier `README.md` présent dans chaque dossier pour comprendre :
- Le rôle du module
- Son utilité dans l'architecture
- Les conventions spécifiques au dossier

## Conventions

Consulter les fichiers de config à la racine (`.eslintrc.json`, `pyproject.toml`) pour les règles de code.
Conventions de nommage : standards Python (PEP 8) et JS.

## Tests

Voir `tests/README.md` pour les commandes et conventions.
Ne jamais modifier le code testé pour faire passer les tests. Si c'est vraiment un bloquage, prévenir l'utilisateur.

## Documentations

Consulter `docs/` pour les guides techniques.
