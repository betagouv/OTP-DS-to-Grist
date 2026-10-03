import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import ColumnElement

from database.models import IpBlocklist
from security.ip_blocklist_store import IpBlocklistStore, _as_epoch


@contextmanager
def _frozen_time(moment):
    """
    Fige l'heure lue par le store, le temps du bloc.

    `security.ip_blocklist_store` utilise le module `time` : c'est donc
    l'horloge du processus qui est figée, pas une horloge locale au store.
    `time.monotonic` reste réel, les tests de validité du cache sont donc
    préservés.
    """
    with patch("time.time", return_value=moment):
        yield


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


def _db_with_row(row):
    """Session mockée dont la recherche par IP renvoie `row`, None pour créer."""
    db = MagicMock()
    db.query.return_value.filter_by.return_value.one_or_none.return_value = row
    return db


class TestIsBanned:
    """
    La lecture passe par le cache, la comparaison se fait sur l'heure courante.
    """

    def test_ip_bannie(self):
        with _frozen_time(1000.0):
            store = _store_with_cache({"203.0.113.7": 2000.0})

            assert store.is_banned("203.0.113.7") is True

    def test_ban_expire(self):
        with _frozen_time(1000.0):
            store = _store_with_cache({"203.0.113.7": 900.0})

            assert store.is_banned("203.0.113.7") is False

    def test_ban_expirant_exactement_maintenant(self):
        with _frozen_time(1000.0):
            store = _store_with_cache({"203.0.113.7": 1000.0})

            assert store.is_banned("203.0.113.7") is False

    def test_ip_sans_ban(self):
        with _frozen_time(1000.0):
            store = _store_with_cache({})

            assert store.is_banned("203.0.113.7") is False

    def test_autre_ip_non_bannie(self):
        with _frozen_time(1000.0):
            store = _store_with_cache({"203.0.113.7": 2000.0})

            assert store.is_banned("198.51.100.1") is False

    def test_sert_le_cache_sans_relire_la_base(self):
        """Le chemin de production ne relit pas la base à chaque appel."""
        with _frozen_time(1000.0):
            store = _store_with_cache({"203.0.113.7": 2000.0})

            store.is_banned("203.0.113.7")

            store._new_session.assert_not_called()

    def test_recharge_la_base_quand_le_cache_a_expire(self):
        store = _store_with_cache({"203.0.113.7": 2000.0}, cache_ttl=60.0)
        store._cache_loaded_at = time.monotonic() - 61.0
        db = MagicMock()
        db.query.return_value.filter.return_value = []
        store._new_session = MagicMock(return_value=db)

        with _frozen_time(1000.0):
            store.is_banned("203.0.113.7")

        store._new_session.assert_called_once()


class TestApplyBan:
    def test_cree_la_ligne_si_absente(self):
        db = _db_with_row(None)
        store = _store_with_db(db)

        with _frozen_time(1000.0):
            store.apply_ban("203.0.113.7")

        db.query.assert_called_once_with(IpBlocklist)
        db.query.return_value.filter_by.assert_called_once_with(ip="203.0.113.7")
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_incremente_le_compteur_d_une_ip_deja_bannie(self):
        existing = _make_row("203.0.113.7", 2, None)
        db = _db_with_row(existing)
        store = _store_with_db(db)

        with _frozen_time(1000.0):
            store.apply_ban("203.0.113.7")

        assert existing.ban_count == 3
        db.add.assert_not_called()

    def test_reutilise_la_ligne_existante(self):
        existing = _make_row("203.0.113.7", 1, None)
        db = _db_with_row(existing)
        store = _store_with_db(db)

        with _frozen_time(1000.0):
            banned_until = store.apply_ban("203.0.113.7")

        assert existing.banned_until == banned_until

    def test_premier_bannissement_dure_une_heure(self):
        db = _db_with_row(None)
        store = _store_with_db(db)

        with _frozen_time(0.0):
            banned_until = store.apply_ban("203.0.113.7")

        assert banned_until - _naive_utc(0.0) == timedelta(hours=1)

    def test_duree_croissant_avec_le_nombre_de_bannissements(self):
        durations = []

        with _frozen_time(0.0):
            for previous_count in (0, 1, 2):
                db = _db_with_row(_make_row("203.0.113.7", previous_count, None))
                store = _store_with_db(db)

                durations.append(store.apply_ban("203.0.113.7"))

        base = _naive_utc(0.0)
        assert durations[0] - base == timedelta(hours=1)
        assert durations[1] - base == timedelta(hours=4)
        assert durations[2] - base == timedelta(hours=16)

    def test_banned_until_en_utc_naive(self):
        db = _db_with_row(None)
        store = _store_with_db(db)

        with _frozen_time(0.0):
            banned_until = store.apply_ban("203.0.113.7")

        assert banned_until.tzinfo is None
        assert banned_until == datetime(1970, 1, 1, 1, 0, 0)

    def test_ferme_la_session(self):
        db = _db_with_row(None)
        store = _store_with_db(db)

        with _frozen_time(1000.0):
            store.apply_ban("203.0.113.7")

        db.close.assert_called_once()

    def test_ferme_la_session_meme_en_cas_d_erreur(self):
        db = _db_with_row(None)
        db.query.side_effect = RuntimeError("base injoignable")
        store = _store_with_db(db)

        with _frozen_time(1000.0), pytest.raises(RuntimeError):
            store.apply_ban("203.0.113.7")

        db.close.assert_called_once()

    def test_invalide_le_cache(self):
        """Seule garantie de fraîcheur : un ban appliqué invalide le cache."""
        db = _db_with_row(None)
        store = _store_with_db(db)
        store._active_bans = {"203.0.113.7": 5000.0}
        store._cache_loaded_at = time.monotonic()

        with _frozen_time(1000.0):
            store.apply_ban("203.0.113.9")

        assert store._active_bans is None


class TestCacheDesBannissements:
    def test_transforme_les_lignes_en_dictionnaire(self):
        moment = 1000.0
        db = MagicMock()
        db.query.return_value.filter.return_value = [
            ("203.0.113.7", moment + 3600),
            ("192.0.2.1", moment + 7200),
        ]
        store = _store_with_db(db)

        with _frozen_time(moment):
            bans = store._get_active_bans()

        assert bans == {"203.0.113.7": moment + 3600, "192.0.2.1": moment + 7200}

    def test_le_filtre_compare_le_meme_epoch_que_la_projection(self):
        """Divergents, le cache garderait des fins de ban que SQL a écartées."""
        moment = 1000.0
        db = MagicMock()
        db.query.return_value.filter.return_value = []
        store = _store_with_db(db)

        with _frozen_time(moment):
            store._get_active_bans()

        _, projete = db.query.call_args.args
        compare = db.query.return_value.filter.call_args.args[0]
        dialect = postgresql.dialect()
        assert str(compare.left.compile(dialect=dialect)) == str(
            projete.compile(dialect=dialect)
        )
        assert compare.right.value == moment

    def test_sert_le_cache_sans_relire_la_base(self):
        store = _store_with_cache({"203.0.113.7": 5000.0}, cache_ttl=60.0)

        assert store._get_active_bans() == {"203.0.113.7": 5000.0}

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


class TestExpressionEpoch:
    """La conversion en epoch est faite par PostgreSQL, pas par Python."""

    def test_compilie_en_sql_postgresql(self):
        sql = str(
            _as_epoch(IpBlocklist.banned_until).compile(dialect=postgresql.dialect())
        )

        assert sql == "CAST(EXTRACT(epoch FROM ip_blocklist.banned_until) AS FLOAT)"

    def test_rend_une_expression_de_type_float(self):
        """L'annotation de retour annonce un `ColumnElement[float]`."""
        expression = _as_epoch(IpBlocklist.banned_until)

        assert isinstance(expression, ColumnElement)
        assert expression.type.python_type is float


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
