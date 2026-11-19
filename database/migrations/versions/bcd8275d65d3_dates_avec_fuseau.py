"""Dates avec fuseau

Passe en `timestamptz` les colonnes de date, jusqu'ici en UTC sans fuseau
(ticket 638) : sync_logs.timestamp, ip_blocklist.banned_until et
otp_config_ips.seen_at. Les valeurs existantes sont lues comme de l'UTC et
gardent leur instant.

La version précédente du code reste correcte tant que le fuseau de la base
est UTC : ses dates sans fuseau y sont lues comme de l'UTC.

Revision ID: bcd8275d65d3
Revises: a2c8e8833cd0
Create Date: 2026-11-19 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "bcd8275d65d3"
down_revision: str | Sequence[str] | None = "a2c8e8833cd0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, colonne, valeur par défaut côté base)
DATE_COLUMNS = (
    ("sync_logs", "timestamp", sa.text("CURRENT_TIMESTAMP")),
    ("ip_blocklist", "banned_until", None),
    ("otp_config_ips", "seen_at", None),
)


def upgrade() -> None:
    for table, column, server_default in DATE_COLUMNS:
        _convert(table, column, server_default, with_timezone=True)


def downgrade() -> None:
    for table, column, server_default in DATE_COLUMNS:
        _convert(table, column, server_default, with_timezone=False)


# --- Fonctions privées ---


def _convert(
    table: str,
    column: str,
    server_default: sa.TextClause | None,
    with_timezone: bool,
) -> None:
    """
    Change le type de la colonne en gardant l'instant : `AT TIME ZONE 'UTC'`
    lit une date sans fuseau comme de l'UTC, et rend une date avec fuseau en
    UTC sans fuseau.
    """
    op.alter_column(
        table,
        column,
        type_=sa.DateTime(timezone=with_timezone),
        existing_type=sa.DateTime(timezone=not with_timezone),
        existing_server_default=server_default,
        postgresql_using=f"\"{column}\" AT TIME ZONE 'UTC'",
    )
