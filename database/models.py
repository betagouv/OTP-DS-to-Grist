from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from datetime import datetime, timezone


class Base(DeclarativeBase):
    pass


class OtpConfiguration(Base):
    __tablename__: str = "otp_configurations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ds_api_token: Mapped[str | None] = mapped_column(String)
    demarche_number: Mapped[str | None] = mapped_column(String)
    grist_base_url: Mapped[str | None] = mapped_column(String)
    grist_api_key: Mapped[str | None] = mapped_column(String)
    grist_doc_id: Mapped[str | None] = mapped_column(String)
    grist_user_id: Mapped[str | None] = mapped_column(String)
    # Filter columns
    filter_date_start: Mapped[str | None] = mapped_column(String)
    filter_date_end: Mapped[str | None] = mapped_column(String)
    filter_statuses: Mapped[str | None] = mapped_column(String)
    filter_groups: Mapped[str | None] = mapped_column(String)


class UserSchedule(Base):
    __tablename__: str = "user_schedules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    otp_config_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("otp_configurations.id", ondelete="SET NULL")
    )
    frequency: Mapped[str | None] = mapped_column(String, default="daily")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_run: Mapped[datetime | None] = mapped_column(DateTime)
    next_run: Mapped[datetime | None] = mapped_column(DateTime)
    last_status: Mapped[str | None] = mapped_column(String)


class SyncLog(Base):
    __tablename__: str = "sync_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grist_user_id: Mapped[str | None] = mapped_column(String)
    grist_doc_id: Mapped[str | None] = mapped_column(String)
    otp_config_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("otp_configurations.id", ondelete="SET NULL")
    )
    demarche_number: Mapped[str | None] = mapped_column(String)
    status: Mapped[str | None] = mapped_column(String)
    message: Mapped[str | None] = mapped_column(String)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    auto: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    success_count: Mapped[int | None] = mapped_column(Integer)
    error_count: Mapped[int | None] = mapped_column(Integer)
