# Documentation

Guides techniques d'OTP.

- [Installation](install.md) : mise en place de l'environnement de développement local
- [Déploiement](deploy.md) : mise en production de l'application
- [Schéma des tables Grist](index.html) : tables et colonnes créées par OTP pour une démarche, avec l'origine des valeurs dans DN

Ce dossier est publié sur GitHub Pages, mais seul `index.html` (le schéma) l'est : `_config.yml` exclut les guides Markdown. Le schéma est une page HTML autonome (design DSFR chargé depuis un CDN). Ses données sont dans le bloc `var D` de `index.html` : à mettre à jour à la main quand les tables ou colonnes créées changent (`schema_utils.py`).
