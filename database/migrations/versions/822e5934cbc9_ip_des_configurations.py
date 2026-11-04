"""IP des configurations

Ajoute la table otp_config_ips : dernier passage de chaque IP sur chaque
configuration, pour l'exploitation (ticket 575). Nouvelle table seulement :
la version précédente du code l'ignore.

Revision ID: 822e5934cbc9
Revises: 1f2e27203e17
Create Date: 2026-11-04 11:30:04.330017

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "822e5934cbc9"
down_revision: str | Sequence[str] | None = "1f2e27203e17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "otp_config_ips",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ip", sa.String(length=45), nullable=False),
        sa.Column("otp_config_id", sa.Integer(), nullable=False),
        sa.Column("seen_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["otp_config_id"], ["otp_configurations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ip", "otp_config_id", name="uq_otp_config_ips_ip_config"),
    )
    op.create_index(
        op.f("ix_otp_config_ips_otp_config_id"),
        "otp_config_ips",
        ["otp_config_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_otp_config_ips_otp_config_id"), table_name="otp_config_ips")
    op.drop_table("otp_config_ips")
