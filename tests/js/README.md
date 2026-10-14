# Tests JavaScript (legacy)

Tests du frontend legacy servi par Flask, exécutés par `npm test` à la racine.
Le front Vue a ses propres tests, gérés indépendamment.

Commandes et conventions générales : voir [../README.md](../README.md).

## Responsabilités

- Vérifier le comportement des modules du frontend legacy dans un DOM simulé.
- Isoler les dépendances externes (appels réseau, contexte Grist, notifications)
  pour tester chaque scénario de façon déterministe.
- Couvrir les cas nominaux ET les cas d'erreur.
