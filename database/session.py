"""
Fabrique de sessions SQLAlchemy partagée par l'application.

Un seul engine, donc un seul pool de connexions, pour tout le process : créer
un engine par appel ouvrirait un pool qui n'est jamais libéré.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from utils.constants import SQLALCHEMY_DATABASE_URL

# pool_pre_ping : une connexion coupée côté serveur (redémarrage, inactivité)
# est détectée et remplacée avant usage
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
