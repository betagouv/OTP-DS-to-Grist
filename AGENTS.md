# AGENTS.md - Guide pour les agents de développement

Ce fichier contient les directives pour les agents IA travaillant sur ce projet.

## Préférences utilisateur

- L'utilisateur parle en français - répondre en français
- Lancer les tests associés après chaque modification
- Demander des clarifications pour toute ambiguïté
- En cas de demande impliquant beaucoup de modifications, proposer un plan en étapes.
  - Ces étapes devraient être testables, sans régression, autonome (ne provoquant pas de régression)

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
