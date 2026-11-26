# front — Nouveau frontend Vue.js

Ce dossier contient la nouvelle application frontend développée avec Vue.js (Vite).

## Rôle

C'est l'interface de l'application : Flask la sert sur `/`, dans la coquille Jinja de
`templates/`. Toutes les fonctionnalités UI y sont développées.

## Installation

```sh
npm install
```

### Mode développement

```sh
npm run dev
```

Le serveur de dev exige `VITE_DEV_ORIGIN` dans le `.env` racine (voir `.env.example`).

### Préparer la production

```sh
npm run build
```

### Lancer les tests

```sh
npm run test
```
