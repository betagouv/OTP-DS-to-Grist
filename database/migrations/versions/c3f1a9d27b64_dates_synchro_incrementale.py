"""Dates de la synchro incrémentale

Ajoute à sync_logs les dates depuis lesquelles la synchronisation suivante
demande à DN les dossiers modifiés et supprimés (ticket 621), jusque-là
enregistrées dans la table Grist Sync_metadata, et un index pour retrouver la
dernière synchronisation d'une configuration. Colonnes nullables seulement : la
version précédente du code les ignore.

Revision ID: c3f1a9d27b64
Revises: a5c6e9e63880
Create Date: 2026-11-20 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3f1a9d27b64"
down_revision: str | Sequence[str] | None = "a5c6e9e63880"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sync_logs",
        sa.Column("modified_dossiers_since", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "sync_logs",
        sa.Column("deleted_dossiers_since", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_sync_logs_otp_config_id_timestamp",
        "sync_logs",
        ["otp_config_id", "timestamp"],
    )


def downgrade() -> None:
    op.drop_index("ix_sync_logs_otp_config_id_timestamp", table_name="sync_logs")
    op.drop_column("sync_logs", "deleted_dossiers_since")
    op.drop_column("sync_logs", "modified_dossiers_since")
