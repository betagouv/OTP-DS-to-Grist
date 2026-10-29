# Tests sur base de données réelle

Tests exécutés contre une vraie base PostgreSQL, sans mock de psycopg2 ni de
SQLAlchemy.

## Rôle

Détecter ce que les tests mockés ne voient pas : une mise à jour de
dépendance (psycopg2, SQLAlchemy, PostgreSQL) qui casse la connexion, la
création du schéma ou les requêtes, ou une divergence entre le schéma créé en
SQL brut par `DatabaseManager` et les modèles ORM de `database/models.py`.

## Conventions

- La base est fournie par `TEST_DATABASE_URL`, distincte de `DATABASE_URL`
  (forcée vers une URL invalide pour les autres suites).
- Ces tests ne sont lancés que par `poe test-db` : `poe test` les exclut et
  reste utilisable sans Docker.
- Garde-fou : le nom de la base doit se terminer par `_test`, les tests
  supprimant les tables de l'application.
- Seule la base est réelle : les autres dépendances externes (API Grist,
  Démarches numériques) restent simulées.
- La base de test est créée automatiquement si elle n'existe pas.
- Chaque test part d'une base vidée de ces tables (fixture `empty_database`).

## Lancer en local

Les tests utilisent le service `db` de docker compose (PostgreSQL 16, version
de la production), dans une base `<nom>_test` distincte de la base de
développement. `poe test-db` démarre le service, attend qu'il accepte les
connexions, puis lance les tests sur l'URL dérivée de `DOCKER_DATABASE_URL`
(secret Codespace ou `.env`). Docker est donc requis, même si l'application
est lancée sans.

```sh
poe test-db
```

Pour cibler une autre base : `TEST_DATABASE_URL=postgresql://…/<nom>_test pytest tests/python/db/`.

## En CI

Le job `test-db` de `.github/workflows/ci.yml` lance `poe test-db` sur une base
jetable, avec des identifiants fixes définis dans le workflow (non secrets).
