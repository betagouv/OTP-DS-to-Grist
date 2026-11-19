"""Erreurs des synchros

Ajoute la colonne sync_logs.errors : erreurs d'une synchro en échec, horodatées,
dans l'ordre (ticket 635). Colonne nullable seulement : la version précédente
du code l'ignore.

Revision ID: a2c8e8833cd0
Revises: 822e5934cbc9
Create Date: 2026-11-17 15:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a2c8e8833cd0"
down_revision: str | Sequence[str] | None = "822e5934cbc9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sync_logs",
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sync_logs", "errors")
