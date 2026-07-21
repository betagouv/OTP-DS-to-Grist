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

## Architecture du projet

### Frontend

Le projet contient deux frontends coexistants :

- **front/ (*nouveau*)** — Application Vue.js (Vite). C'est la cible pour toutes les
  nouvelles fonctionnalités (ex: gestion multi-démarches).
- **templates/ + static/js/ (*legacy*)** — Ancien frontend Flask/Jinja. À conserver
  jusqu'à migration complète. S'inspirer de son fonctionnement pour les fonctionnalités
  manquantes dans front/.

**Règles :**
- Les nouvelles fonctionnalités UI vont dans `front/` (Vue.js)
- Les modifications du front legacy se limitent au correctif ou au portage vers `front/`
- Le code partagé entre les deux (dans `static/js/`) doit être maintenu et testé via les
  tests unitaires existants
- Toujours vérifier si une fonctionnalité demandée existe déjà dans le legacy avant de la
  coder from scratch

### Contexte d'évolution

L'application gère initialement une synchronisation unique (une démarche DS vers un document Grist).
L'évolution en cours consiste à supporter la **gestion multi-configurations** (plusieurs paires
DS ↔ Grist) par utilisateur. Le backend supporte déjà le multi-config (`otp_configurations`,
`ConfigManager`), mais le front-end est encore en phase de migration : le legacy (templates/)
reste single-config, le nouveau front (`front/`) vise le multi-config et est en cours de
développement. Toute intervention doit considérer cette trajectoire.

## Contexte du projet

Ce projet a été initialement créé par un non-développeur avec assistance IA.

Il en résulte un code à remanier et des opportunités de refactoring régulières.

**Merci de :**
- Proposer des remaniements (refactoring) quand une opportunité est identifiée
- Simplifier le code quand une meilleure approche est trouvée
- Ne pas hésiter à réorganiser les fichiers si ça améliore la structure et regroupe des responsabilités
- Vérifier si une responsabilité est déjà existante et l'utiliser ou la faire évoluer

## Prérequis avant toute intervention

Avant de lire, créer ou modifier un fichier, vérifier qu'un `README.md` existe dans :
- Le dossier du fichier concerné
- Les dossiers parents immédiats (jusqu'à la racine du module)
- Préviens moi si un fichier `README.md` n'est pas présent

Le lire en premier — sans exception. Il peut contenir :
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
