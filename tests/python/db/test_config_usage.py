import time

import pytest
from sqlalchemy import func, select

from configuration.config_usage import ConfigUsage
from database.models import OtpConfigIp, OtpConfiguration

IP = "203.0.113.7"


@pytest.fixture
def otp_config_id(db_session) -> int:
    otp_config = OtpConfiguration(grist_user_id="userA", grist_doc_id="docA")
    db_session.add(otp_config)
    db_session.commit()

    return otp_config.id


class TestMarkUsed:
    """Date du dernier passage enregistrée dans la table otp_config_ips réelle"""

    def test_records_current_instant(self, db_session, otp_config_id):
        before = time.time()

        ConfigUsage().mark_used(IP, [otp_config_id])

        # L'epoch calculé par PostgreSQL désigne l'instant, quel que soit le
        # type de la colonne (avec ou sans fuseau)
        seen_at = db_session.scalar(
            select(func.extract("epoch", OtpConfigIp.seen_at)).where(
                OtpConfigIp.ip == IP, OtpConfigIp.otp_config_id == otp_config_id
            )
        )
        assert before - 1 <= float(seen_at) <= time.time() + 1
