# Tests Python

Tests du backend, exécutés par `poe test` à la racine.

Structure (unitaires / intégration), commandes et conventions générales :
voir [../README.md](../README.md).

## Responsabilités

- Fournir aux suites un contexte de test commun (configuration de départ,
  gestionnaire de configuration et authentification simulés) réutilisé par les
  tests, plutôt que chaque test le recrée de son côté.
- Garantir l'isolation : aucune dépendance externe réelle (réseau, base de
  production) n'est sollicitée pendant les tests. Seule exception : `db/`,
  sur une base de test dédiée fournie explicitement.
- Couvrir les cas nominaux ET les cas d'erreur.
