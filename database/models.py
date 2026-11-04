from sqlalchemy import (
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    false,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from datetime import datetime, timezone


# Les modèles décrivent la base telle qu'elle existe : colonnes TEXT, valeurs
# par défaut côté base (server_default) en plus de celles appliquées par l'ORM.
# tests/python/db/test_models.py vérifie qu'Alembic n'y détecte aucun écart.


class Base(DeclarativeBase):
    pass


class OtpConfiguration(Base):
    __tablename__: str = "otp_configurations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ds_api_token: Mapped[str | None] = mapped_column(Text)
    demarche_number: Mapped[str | None] = mapped_column(Text)
    grist_base_url: Mapped[str | None] = mapped_column(Text)
    grist_api_key: Mapped[str | None] = mapped_column(Text)
    grist_doc_id: Mapped[str | None] = mapped_column(Text)
    grist_user_id: Mapped[str | None] = mapped_column(Text, server_default="")
    grist_user_email: Mapped[str | None] = mapped_column(Text)
    # Filter columns
    filter_date_start: Mapped[str | None] = mapped_column(Text)
    filter_date_end: Mapped[str | None] = mapped_column(Text)
    filter_statuses: Mapped[str | None] = mapped_column(Text)
    filter_groups: Mapped[str | None] = mapped_column(Text)


class UserSchedule(Base):
    __tablename__: str = "user_schedules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    otp_config_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("otp_configurations.id", ondelete="SET NULL")
    )
    frequency: Mapped[str | None] = mapped_column(
        Text, default="daily", server_default="daily"
    )
    enabled: Mapped[bool | None] = mapped_column(
        Boolean, default=False, server_default=false()
    )


class SyncLog(Base):
    __tablename__: str = "sync_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grist_user_id: Mapped[str | None] = mapped_column(Text)
    grist_doc_id: Mapped[str | None] = mapped_column(Text)
    otp_config_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("otp_configurations.id", ondelete="SET NULL")
    )
    demarche_number: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime | None] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    auto: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true(), nullable=False
    )
    success_count: Mapped[int | None] = mapped_column(Integer)
    error_count: Mapped[int | None] = mapped_column(Integer)
    # Métadonnées de la synchronisation (ticket 567) : NULL sur les lignes
    # historiques et sur les échecs survenus avant leur calcul
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    force_full_sync: Mapped[bool | None] = mapped_column(Boolean)
    filters_hash: Mapped[str | None] = mapped_column(Text)


class IpBlocklist(Base):
    __tablename__: str = "ip_blocklist"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ip: Mapped[str] = mapped_column(String(45), unique=True)
    ban_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    banned_until: Mapped[datetime | None] = mapped_column(DateTime)
