import time
from unittest.mock import patch

import pytest

from database.models import IpBlocklist
from security.ip_blocklist import ban_duration
from security.ip_blocklist_store import IpBlocklistStore
from utils.constants import SQLALCHEMY_DATABASE_URL

IP = "203.0.113.7"


@pytest.fixture
def store(initialized_database) -> IpBlocklistStore:
    # Même URL que app.py ; sans cache : chaque lecture interroge la base
    return IpBlocklistStore(SQLALCHEMY_DATABASE_URL, cache_ttl=0)


class TestApplyBan:
    """Persistance des bannissements sur une vraie base"""

    def test_unknown_ip_is_not_banned(self, store):
        assert store.is_banned(IP) is False

    def test_banned_ip_is_banned(self, store):
        store.apply_ban(IP)

        assert store.is_banned(IP) is True

    def test_repeated_ban_increments_count_and_lasts_longer(self, store, db_session):
        first_until = store.apply_ban(IP)
        second_until = store.apply_ban(IP)

        row = db_session.query(IpBlocklist).filter_by(ip=IP).one()

        assert row.ban_count == 2
        assert row.banned_until == second_until
        assert second_until - first_until >= ban_duration(2) - ban_duration(1)


class TestBanExpiration:
    """La fin de ban est comparée en epoch par PostgreSQL"""

    def test_ban_expires_after_its_duration(self, store):
        store.apply_ban(IP)
        after_ban = time.time() + ban_duration(1).total_seconds() + 1

        with patch("security.ip_blocklist_store.time.time", return_value=after_ban):
            assert store.is_banned(IP) is False

    def test_ban_still_active_just_before_its_end(self, store):
        store.apply_ban(IP)
        before_end = time.time() + ban_duration(1).total_seconds() - 60

        with patch("security.ip_blocklist_store.time.time", return_value=before_end):
            assert store.is_banned(IP) is True
