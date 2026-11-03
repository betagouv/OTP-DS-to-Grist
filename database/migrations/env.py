"""
Environnement d'exécution des migrations Alembic.

La base cible est celle de l'application (DATABASE_URL, via
utils/constants.py) et la référence de l'autogénération est l'ensemble des
modèles ORM (database/models.py).
"""

import logging

from alembic import context
from sqlalchemy import create_engine, pool

from database.models import Base
from utils.constants import SQLALCHEMY_DATABASE_URL

config = context.config

# Sans alembic.ini, aucune configuration de logs n'est chargée : en ligne de
# commande, on affiche les migrations appliquées. Appelé par le code (tests),
# config.cmd_opts est absent et la configuration de l'appelant est respectée.
if config.cmd_opts is not None:
    logging.basicConfig(format="%(levelname)s [%(name)s] %(message)s")
    logging.getLogger("alembic").setLevel(logging.INFO)

if context.is_offline_mode():
    # La migration initiale interroge la base (information_schema) : elle ne
    # peut pas être rendue en SQL sans connexion
    raise RuntimeError("Mode hors ligne (--sql) non pris en charge")

engine = create_engine(SQLALCHEMY_DATABASE_URL, poolclass=pool.NullPool)

with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        # Mêmes critères que tests/python/db/test_models.py
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()
