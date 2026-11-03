# Migrations du schéma

Migrations de la base PostgreSQL, gérées par [Alembic](https://alembic.sqlalchemy.org/).

## Rôle

Faire évoluer le schéma de façon versionnée : chaque migration est un script de
`versions/`, appliqué une seule fois par base. Alembic enregistre dans la table
`alembic_version` la dernière migration appliquée.

Les modèles ORM (`database/models.py`) sont la référence du schéma : les
migrations sont générées à partir de leur écart avec la base, et
`tests/python/db/` vérifie que les migrations appliquées aboutissent exactement
aux modèles.

## Conventions

- Configuration dans `pyproject.toml` (`[tool.alembic]`), sans `alembic.ini`.
  La base cible est `DATABASE_URL` (voir `env.py`).
- La migration initiale reprend les migrations maison de `DatabaseManager` et
  reste idempotente : elle met à niveau une base existante quel que soit son
  état historique, sans `alembic stamp`.
- Le mode hors ligne (`--sql`) n'est pas pris en charge.

## Commandes

```sh
poe migrate                                   # applique les migrations en attente
alembic revision --autogenerate -m "<sujet>"  # génère une migration depuis les modèles
alembic check                                 # vérifie que la base correspond aux modèles
alembic current                               # version appliquée sur la base
```

Une migration autogénérée est un brouillon à relire avant de la committer :
un renommage y apparaît comme une suppression suivie d'un ajout (perte des
données), et les migrations de données s'écrivent à la main.
