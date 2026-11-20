"""Fuseau de la base

Règle le fuseau de la base sur Europe/Paris (ticket 638) : psql et toute
nouvelle connexion affichent les dates à l'heure de Paris. Les connexions déjà
ouvertes gardent leur fuseau.

Le code écrit des dates avec fuseau depuis la révision bcd8275d65d3 : il ne
dépend pas du fuseau de la base. Risque accepté : déployée en même temps que
bcd8275d65d3, une version antérieure du code qui tourne pendant la migration
peut écrire banned_until ou seen_at sans fuseau sur une nouvelle connexion ;
la date est alors lue à l'heure de Paris, trop tôt de 1 h (hiver) ou 2 h (été).

Revision ID: a5c6e9e63880
Revises: bcd8275d65d3
Create Date: 2026-11-19 17:00:00.000000

"""

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a5c6e9e63880"
down_revision: str | Sequence[str] | None = "bcd8275d65d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DATABASE_TIMEZONE = "Europe/Paris"


def upgrade() -> None:
    _alter_database(f"SET timezone TO ''{DATABASE_TIMEZONE}''")


def downgrade() -> None:
    _alter_database("RESET timezone")


# --- Fonctions privées ---


def _alter_database(setting: str) -> None:
    """
    Applique le réglage à la base courante : son nom varie selon
    l'environnement, ALTER DATABASE l'exige pourtant en toutes lettres.
    """
    op.execute(
        "DO $$ BEGIN EXECUTE 'ALTER DATABASE ' || quote_ident(current_database())"
        f" || ' {setting}'; END $$"
    )
