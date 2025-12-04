from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey
)
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone

Base = declarative_base()


class OtpConfiguration(Base):
    __tablename__ = 'otp_configurations'
    id = Column(Integer, primary_key=True)
    ds_api_token = Column(String)
    demarche_number = Column(String)
    grist_base_url = Column(String)
    grist_api_key = Column(String)
    grist_doc_id = Column(String)
    grist_user_id = Column(String)
    # Filter columns
    filter_date_start = Column(String)
    filter_date_end = Column(String)
    filter_statuses = Column(String)
    filter_groups = Column(String)


class UserSchedule(Base):
    __tablename__ = 'user_schedules'
    id = Column(Integer, primary_key=True)
    otp_config_id = Column(
        Integer,
        ForeignKey('otp_configurations.id', ondelete='SET NULL')
    )
    frequency = Column(String, default='daily')
    enabled = Column(Boolean, default=False)
    last_run = Column(DateTime)
    next_run = Column(DateTime)
    last_status = Column(String)


class SyncLog(Base):
    __tablename__ = 'sync_logs'
    id = Column(Integer, primary_key=True)
    grist_user_id = Column(String)
    grist_doc_id = Column(String)
    status = Column(String)
    message = Column(String)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
