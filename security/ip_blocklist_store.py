import time
from datetime import datetime, timezone

from sqlalchemy import Float, create_engine, func
from sqlalchemy.orm import InstrumentedAttribute, sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from database.models import IpBlocklist
from security.ip_blocklist import ban_duration

DEFAULT_CACHE_TTL = 60.0


def _as_epoch(
    column: InstrumentedAttribute[datetime | None]
) -> ColumnElement[float]:
    """
    Convertit une colonne DateTime en secondes via PostgreSQL.
    """
    return func.extract("epoch", column).cast(Float)


class IpBlocklistStore:
    """
    Persistance des bannissements d'IP.

    Le store ne porte que ce qui doit survivre à un redémarrage de
    l'instance : le numéro de bannissement et la fin de ban. Les compteurs
    de la fenêtre glissante restent en mémoire (voir `security.ip_blocklist`),
    ils repartent donc de zéro à chaque redémarrage.

    Une seule ligne par IP, jamais purgée : un bannissement expiré est
    filtré à la lecture, et sa présence permet au bannissement suivant de
    durer plus longtemps.

    Args:
        database_url: URL de connexion PostgreSQL
        cache_ttl: Durée de validité du cache des bannissements actifs, en
            secondes. Le cache évite une lecture de base sur chaque requête,
            ce qui est nécessaire car psycopg2 est bloquant et l'application
            ne tourne qu'avec un seul worker.
    """

    def __init__(self, database_url: str, cache_ttl: float = DEFAULT_CACHE_TTL):
        self._database_url = database_url
        self._cache_ttl = cache_ttl
        self._engine = None
        self._session_factory = None
        self._active_bans = None
        self._cache_loaded_at = None

    @staticmethod
    def _as_naive_utc(moment: datetime) -> datetime:
        """
        Normalise un datetime vers UTC naïve, convention des colonnes DateTime.
        """
        if moment.tzinfo is None:
            return moment

        return moment.astimezone(timezone.utc).replace(tzinfo=None)

    def _new_session(self):
        """Crée une session, en initialisant le moteur au premier usage."""
        if self._session_factory is None:
            self._engine = create_engine(self._database_url)
            self._session_factory = sessionmaker(
                autocommit=False, autoflush=False, bind=self._engine
            )

        return self._session_factory()

    def is_banned(self, ip: str) -> bool:
        banned_until = self._get_active_bans().get(ip)

        return banned_until is not None and banned_until > time.time()

    def apply_ban(self, ip: str) -> datetime:
        """
        Bannis une IP pour une durée dépendant de son nombre de bannissements.

        Le compteur est lu puis incrémenté : la durée vient de `ban_duration`,
        jamais d'un calcul SQL, pour ne pas dupliquer la règle en base.
        """
        moment = self._as_naive_utc(datetime.fromtimestamp(
            time.time(),
            timezone.utc
        ))

        db = self._new_session()

        try:
            row = db.query(IpBlocklist).filter_by(ip=ip).one_or_none()
            ban_count = (row.ban_count if row else 0) + 1
            banned_until = moment + ban_duration(ban_count)

            if row is None:
                row = IpBlocklist(
                    ip=ip,
                    ban_count=ban_count,
                    banned_until=banned_until
                )
                db.add(row)
            else:
                row.ban_count = ban_count
                row.banned_until = banned_until

            db.commit()
        finally:
            db.close()

        self._active_bans = None

        return banned_until

    def _get_active_bans(self) -> dict[str, float]:
        if self._active_bans is not None:
            age = time.monotonic() - self._cache_loaded_at
            if age < self._cache_ttl:
                return self._active_bans

        moment = time.time()
        epoch = _as_epoch(IpBlocklist.banned_until)

        db = self._new_session()
        try:
            # La sélection se fait en epoch : PostgreSQL compare
            # et le store ne voit que des `float`.
            # Les lignes sans bannissement donnent NULL
            # et sont donc exclues par la comparaison
            query = db.query(IpBlocklist.ip, epoch).filter(epoch > moment)
            bans = dict(query)
        finally:
            db.close()

        self._active_bans = bans
        self._cache_loaded_at = time.monotonic()

        return bans
