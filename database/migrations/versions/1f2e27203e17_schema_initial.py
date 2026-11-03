"""Schéma initial

Reprend les migrations maison de DatabaseManager.create_table_if_not_exists
(supprimé depuis), les ajouts de colonnes d'une même table étant regroupés.
Idempotente : sur une base vide elle crée le schéma, sur une base déjà
déployée elle la met à niveau quel que soit son état historique. C'est ce qui
permet la bascule vers Alembic par un simple `alembic upgrade head`, sans
`stamp`.

Revision ID: 1f2e27203e17
Revises:
Create Date: 2026-11-03 10:24:28.425841

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1f2e27203e17"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS otp_configurations (
            id SERIAL PRIMARY KEY,
            ds_api_token TEXT,
            demarche_number TEXT,
            grist_base_url TEXT,
            grist_api_key TEXT,
            grist_doc_id TEXT
        )
    """)

    # Bases antérieures à la clé primaire : ajout de la colonne id
    id_column_query = sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'otp_configurations' AND column_name = 'id'
    """)
    has_id = op.get_bind().execute(id_column_query).first()
    if not has_id:
        op.execute("ALTER TABLE otp_configurations ADD COLUMN id SERIAL PRIMARY KEY")

    op.execute("""
        ALTER TABLE otp_configurations
            ADD COLUMN IF NOT EXISTS grist_user_id TEXT DEFAULT '',
            ADD COLUMN IF NOT EXISTS grist_user_email TEXT,
            ADD COLUMN IF NOT EXISTS filter_date_start TEXT,
            ADD COLUMN IF NOT EXISTS filter_date_end TEXT,
            ADD COLUMN IF NOT EXISTS filter_statuses TEXT,
            ADD COLUMN IF NOT EXISTS filter_groups TEXT
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS user_schedules (
            id SERIAL PRIMARY KEY,
            otp_config_id INTEGER,
            frequency TEXT DEFAULT 'daily',
            enabled BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (otp_config_id) REFERENCES otp_configurations(id) ON DELETE SET NULL
        )
    """)

    # Ticket 569 : next_run/last_run/last_status n'étaient jamais lues
    # (l'API se sert du scheduler) et doublonnent sync_logs
    op.execute("""
        ALTER TABLE user_schedules
            DROP COLUMN IF EXISTS next_run,
            DROP COLUMN IF EXISTS last_run,
            DROP COLUMN IF EXISTS last_status
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS sync_logs (
            id SERIAL PRIMARY KEY,
            grist_user_id TEXT,
            grist_doc_id TEXT,
            status TEXT,
            message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Multi-démarche, compteurs de dossiers et métadonnées de la
    # synchronisation (ticket 567)
    op.execute("""
        ALTER TABLE sync_logs
            ADD COLUMN IF NOT EXISTS otp_config_id INTEGER
                REFERENCES otp_configurations(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS demarche_number TEXT,
            ADD COLUMN IF NOT EXISTS auto BOOLEAN DEFAULT TRUE NOT NULL,
            ADD COLUMN IF NOT EXISTS success_count INTEGER,
            ADD COLUMN IF NOT EXISTS error_count INTEGER,
            ADD COLUMN IF NOT EXISTS duration_seconds FLOAT,
            ADD COLUMN IF NOT EXISTS force_full_sync BOOLEAN,
            ADD COLUMN IF NOT EXISTS filters_hash TEXT
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS ip_blocklist (
            id SERIAL PRIMARY KEY,
            ip VARCHAR(45) NOT NULL UNIQUE,
            ban_count INTEGER NOT NULL DEFAULT 0,
            banned_until TIMESTAMP
        )
    """)


def downgrade() -> None:
    op.drop_table("ip_blocklist")
    op.drop_table("sync_logs")
    op.drop_table("user_schedules")
    op.drop_table("otp_configurations")
