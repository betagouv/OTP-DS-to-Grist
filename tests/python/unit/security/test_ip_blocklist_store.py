import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from database.models import IpBlocklist
from security.ip_blocklist_store import IpBlocklistStore


def _naive_utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).replace(tzinfo=None)


def _store_with_cache(active_bans, cache_ttl=60.0):
    """Store dont le cache est déjà rempli, sans accès à la base."""
    store = IpBlocklistStore("url", cache_ttl=cache_ttl)
    store._active_bans = active_bans
    store._cache_loaded_at = time.monotonic()
    store._new_session = MagicMock()
    return store


def _store_with_db(db, cache_ttl=60.0):
    """Store dont la session est mockée et le cache vide."""
    store = IpBlocklistStore("url", cache_ttl=cache_ttl)
    store._new_session = MagicMock(return_value=db)
    return store


def _make_row(ip, ban_count, banned_until):
    row = MagicMock(spec=IpBlocklist)
    row.ip = ip
    row.ban_count = ban_count
    row.banned_until = banned_until
    return row


class TestIsBanned:
    def test_ip_bannie(self):
        store = _store_with_cache({"203.0.113.7": 2000.0})
        assert store.is_banned("203.0.113.7", now=1000.0) is True

    def test_ban_expire(self):
        store = _store_with_cache({"203.0.113.7": 1000.0})
        assert store.is_banned("203.0.113.7", now=2000.0) is False

    def test_ip_non_bannie(self):
        store = _store_with_cache({"203.0.113.7": 5000.0})
        assert store.is_banned("198.51.100.1", now=1000.0) is False

    def test_cache_vide(self):
        store = _store_with_cache({})
        assert store.is_banned("203.0.113.7", now=1000.0) is False

    def test_ban_expirant_exactement_maintenant(self):
        store = _store_with_cache({"203.0.113.7": 1000.0})
        assert store.is_banned("203.0.113.7", now=1000.0) is False

    def test_recharge_la_base_quand_le_cache_a_expire(self):
        store = _store_with_cache({"203.0.113.7": 5000.0}, cache_ttl=60.0)
        store._cache_loaded_at = time.monotonic() - 61.0
        db = MagicMock()
        store._new_session = MagicMock(return_value=db)
        db.query.return_value.filter.return_value = []

        store.is_banned("203.0.113.7", now=1000.0)

        store._new_session.assert_called_once()


class TestApplyBan:
    def test_cree_la_ligne_si_absente(self):
        db = MagicMock()
        db.get.return_value = None
        store = _store_with_db(db)

        store.apply_ban("203.0.113.7", now=1000.0)

        db.get.assert_called_once_with(IpBlocklist, "203.0.113.7")
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_incremente_le_compteur_d_une_ip_deja_bannie(self):
        existing = _make_row("203.0.113.7", 2, None)
        db = MagicMock()
        db.get.return_value = existing
        store = _store_with_db(db)

        store.apply_ban("203.0.113.7", now=1000.0)

        assert existing.ban_count == 3
        db.add.assert_not_called()

    def test_reutilise_la_ligne_existante(self):
        existing = _make_row("203.0.113.7", 1, None)
        db = MagicMock()
        db.get.return_value = existing
        store = _store_with_db(db)

        banned_until = store.apply_ban("203.0.113.7", now=1000.0)

        assert existing.banned_until == banned_until

    def test_premier_bannissement_dure_une_heure(self):
        db = MagicMock()
        db.get.return_value = None
        store = _store_with_db(db)

        banned_until = store.apply_ban("203.0.113.7", now=0.0)

        assert banned_until - _naive_utc(0.0) == timedelta(hours=1)

    def test_duree_croissant_avec_le_nombre_de_bannissements(self):
        durations = []
        for previous_count in (0, 1, 2):
            db = MagicMock()
            db.get.return_value = _make_row("203.0.113.7", previous_count, None)
            store = _store_with_db(db)

            durations.append(store.apply_ban("203.0.113.7", now=0.0))

        base = _naive_utc(0.0)
        assert durations[0] - base == timedelta(hours=1)
        assert durations[1] - base == timedelta(hours=4)
        assert durations[2] - base == timedelta(hours=16)

    def test_banned_until_en_utc_naive(self):
        db = MagicMock()
        db.get.return_value = None
        store = _store_with_db(db)

        banned_until = store.apply_ban("203.0.113.7", now=0.0)

        assert banned_until.tzinfo is None
        assert banned_until == datetime(1970, 1, 1, 1, 0, 0)

    def test_ferme_la_session(self):
        db = MagicMock()
        db.get.return_value = None
        store = _store_with_db(db)

        store.apply_ban("203.0.113.7", now=1000.0)

        db.close.assert_called_once()

    def test_ferme_la_session_meme_en_cas_d_erreur(self):
        db = MagicMock()
        db.get.side_effect = RuntimeError("base injoignable")
        store = _store_with_db(db)

        with pytest.raises(RuntimeError):
            store.apply_ban("203.0.113.7", now=1000.0)

        db.close.assert_called_once()

    def test_invalide_le_cache(self):
        db = MagicMock()
        db.get.return_value = None
        store = _store_with_db(db)
        store._active_bans = {"203.0.113.7": 5000.0}
        store._cache_loaded_at = time.monotonic()

        store.apply_ban("203.0.113.9", now=1000.0)

        assert store._active_bans is None


class TestCacheDesBannissements:
    def test_charge_les_bannissements_actifs_depuis_la_base(self):
        now = time.time()
        db = MagicMock()
        db.query.return_value.filter.return_value = [
            _make_row("203.0.113.7", 1, _naive_utc(now + 3600)),
            _make_row("198.51.100.1", 1, _naive_utc(now - 3600)),
            _make_row("192.0.2.1", 1, _naive_utc(now + 7200)),
        ]
        store = _store_with_db(db)

        bans = store._get_active_bans()

        assert set(bans) == {"203.0.113.7", "192.0.2.1"}

    def test_les_fins_de_ban_sont_des_timestamps(self):
        now = time.time()
        db = MagicMock()
        db.query.return_value.filter.return_value = [
            _make_row("203.0.113.7", 1, _naive_utc(now + 3600)),
        ]
        store = _store_with_db(db)

        bans = store._get_active_bans()

        assert bans["203.0.113.7"] == pytest.approx(now + 3600, abs=1)

    def test_ignore_les_lignes_sans_ban(self):
        db = MagicMock()
        db.query.return_value.filter.return_value = [
            _make_row("203.0.113.7", 1, None),
        ]
        store = _store_with_db(db)

        assert store._get_active_bans() == {}

    def test_ignore_les_bans_expires(self):
        db = MagicMock()
        db.query.return_value.filter.return_value = []
        store = _store_with_db(db)

        assert store._get_active_bans() == {}

    def test_sert_le_cache_sans_relire_la_base(self):
        store = _store_with_cache({"203.0.113.7": 5000.0}, cache_ttl=60.0)

        assert store._get_active_bans() == {"203.0.113.7": 5000.0}
        store._new_session.assert_not_called()

    def test_recharge_apres_expiration_du_cache(self):
        store = _store_with_cache({"203.0.113.7": 5000.0}, cache_ttl=60.0)
        store._cache_loaded_at = time.monotonic() - 61.0
        db = MagicMock()
        db.query.return_value.filter.return_value = []
        store._new_session = MagicMock(return_value=db)

        store._get_active_bans()

        store._new_session.assert_called_once()

    def test_derniere_borne_de_validite(self):
        store = _store_with_cache({"203.0.113.7": 5000.0}, cache_ttl=60.0)
        store._cache_loaded_at = time.monotonic() - 59.0

        store._get_active_bans()

        store._new_session.assert_not_called()

    def test_ferme_la_session(self):
        db = MagicMock()
        db.query.return_value.filter.return_value = []
        store = _store_with_db(db)

        store._get_active_bans()

        db.close.assert_called_once()

    def test_ferme_la_session_meme_en_cas_d_erreur(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("base injoignable")
        store = _store_with_db(db)

        with pytest.raises(RuntimeError):
            store._get_active_bans()

        db.close.assert_called_once()


class TestMoteurParesseux:
    @patch("security.ip_blocklist_store.create_engine")
    @patch("security.ip_blocklist_store.sessionmaker")
    def test_aucun_moteur_tant_que_le_store_n_est_pas_utilise(
        self, mock_sessionmaker, mock_create_engine
    ):
        store = IpBlocklistStore("url")

        assert store._session_factory is None
        mock_create_engine.assert_not_called()
        mock_sessionmaker.assert_not_called()

    @patch("security.ip_blocklist_store.create_engine")
    @patch("security.ip_blocklist_store.sessionmaker")
    def test_moteur_cree_au_premier_usage(self, mock_sessionmaker, mock_create_engine):
        store = IpBlocklistStore("url")

        store._new_session()

        mock_create_engine.assert_called_once_with("url")
        assert store._session_factory is mock_sessionmaker.return_value

    @patch("security.ip_blocklist_store.create_engine")
    @patch("security.ip_blocklist_store.sessionmaker")
    def test_moteur_reutilise_ensuite(self, mock_sessionmaker, mock_create_engine):
        store = IpBlocklistStore("url")

        store._new_session()
        store._new_session()

        mock_create_engine.assert_called_once()