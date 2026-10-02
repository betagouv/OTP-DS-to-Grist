import time
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import IpBlocklist
from security.ip_blocklist import ban_duration

DEFAULT_CACHE_TTL = 60.0


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

    def is_banned(self, ip: str, now: float | None = None) -> bool:
        """
        Indique si une IP est actuellement bannie.

        Args:
            ip: Adresse IP normalisée
            now: Timestamp de référence (epoch, en secondes), par défaut
                l'heure courante

        Returns:
            True si un bannissement est encore actif
        """
        moment = time.time() if now is None else now
        bans = self._get_active_bans()
        banned_until = bans.get(ip)

        return banned_until is not None and banned_until > moment

    def apply_ban(self, ip: str, now: float | None = None) -> datetime:
        """
        Bannis une IP pour une durée dépendant de son nombre de bannissements.

        Le compteur est lu puis incrémenté : la durée vient de `ban_duration`,
        jamais d'un calcul SQL, pour ne pas dupliquer la règle en base.

        Args:
            ip: Adresse IP normalisée
            now: Timestamp du bannissement (epoch, en secondes), par défaut
                l'heure courante

        Returns:
            Fin du bannissement, en UTC naïve
        """
        moment = time.time() if now is None else now
        now_naive = self._as_naive_utc(datetime.fromtimestamp(moment, timezone.utc))

        db = self._new_session()

        try:
            row = db.get(IpBlocklist, ip)
            ban_count = (row.ban_count if row else 0) + 1
            banned_until = now_naive + ban_duration(ban_count)

            if row is None:
                row = IpBlocklist(ip=ip, ban_count=ban_count, banned_until=banned_until)
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
        """
        Bannissements encore actifs, sous forme d'un cache ip -> fin de ban (epoch).

        Le cache est reconstruit dès qu'il a plus de `cache_ttl`. Un
        bannissement appliqué entre deux rechargements invalide le cache, donc
        il s'applique immédiatement sans attendre l'expiration.
        """
        if self._active_bans is not None:
            age = time.monotonic() - self._cache_loaded_at
            if age < self._cache_ttl:
                return self._active_bans

        db = self._new_session()
        try:
            now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
            bans = {}
            query = db.query(IpBlocklist).filter(IpBlocklist.banned_until.isnot(None))

            for row in query:
                if row.banned_until is None or row.banned_until <= now_naive:
                    continue
                bans[row.ip] = row.banned_until.replace(
                    tzinfo=timezone.utc
                ).timestamp()
        finally:
            db.close()

        self._active_bans = bans
        self._cache_loaded_at = time.monotonic()

        return bans
