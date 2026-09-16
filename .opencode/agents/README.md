---
disable: true
---

# Agents opencode du projet

Ce dossier contient les agents opencode dédiés à l'analyse du dépôt.
Chaque agent est un fichier `<nom>.md` dont le corps sert de prompt.

Tous les agents respectent le même gabarit :

- Frontmatter avec `description`, `mode: subagent` et `permission.edit: deny` (lecture seule).
- Sortie en deux catégories : « À changer » (problème à corriger) et « Opinion » (amélioration possible).
- Aucune modification de fichier, réponses en français, pas de remarques spéculatives.

Chaque agent est indépendant : les rôles sont complémentaires et ne doivent pas
se chevaucher.
