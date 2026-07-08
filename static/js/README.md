# JavaScript

Ce dossier contient le code JavaScript côté client.

## Public

**Attention** : Ce dossier est accessible publiquement depuis le navigateur.
Ne jamais y inclure de données sensibles (tokens, clés API).

Note : Du JavaScript peut aussi être présent dans les templates.

## Code partagé entre les deux frontends

Une partie de ce code est utilisée à la fois par le front legacy (templates Flask/Jinja & js dans static/js)
et par le nouveau frontend Vue.js (`front/`).

Conséquence : toute modification doit être testée via les tests unitaires existants et ne pas casser l'un ou l'autre frontend.
