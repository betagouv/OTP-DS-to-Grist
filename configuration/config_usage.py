"""
Trace de l'utilisation des configurations : quelle IP a utilisé quelle
configuration, et quand pour la dernière fois (table `otp_config_ips`).

Cette trace sert l'exploitation (`poe inspect`), pas le fonctionnement de
l'application.
"""

import time
from collections.abc import Callable, Iterable
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from database.models import OtpConfigIp
from database.session import SessionLocal

# Un même couple (IP, configuration) n'est réécrit en base qu'après ce délai :
# la date du dernier passage reste précise à 4 h près, sans écriture à chaque
# requête (psycopg2 est bloquant et l'application n'a qu'un worker)
REFRESH_DELAY_SECONDS = 4 * 3600


class ConfigUsage:
    """
    Retient qu'une IP a utilisé des configurations.

    Les couples récemment notés sont gardés en mémoire : un redémarrage les
    oublie, ce qui coûte au pire une écriture de plus par couple.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session] = SessionLocal,
        refresh_delay: float = REFRESH_DELAY_SECONDS,
    ):
        self._session_factory = session_factory
        self._refresh_delay = refresh_delay
        self._marked_at: dict[tuple[str, int], float] = {}

    def mark_used(self, ip: str, otp_config_ids: Iterable[int]) -> None:
        """Note que l'IP vient d'utiliser ces configurations."""
        now = time.monotonic()
        recent = self._recently_marked(now)
        pairs = [
            (ip, otp_config_id)
            for otp_config_id in dict.fromkeys(otp_config_ids)
            if (ip, otp_config_id) not in recent
        ]

        if pairs:
            self._save(pairs)

        self._marked_at = {**recent, **{pair: now for pair in pairs}}

    # --- Méthodes privées ---

    def _recently_marked(self, now: float) -> dict[tuple[str, int], float]:
        """Couples notés depuis moins que le délai ; les autres sont oubliés."""
        return {
            pair: marked_at
            for pair, marked_at in self._marked_at.items()
            if now - marked_at < self._refresh_delay
        }

    def _save(self, pairs: list[tuple[str, int]]) -> None:
        """Crée les couples absents, met à jour la date des autres."""
        # Colonnes DateTime en UTC naïf, comme les autres tables
        seen_at = datetime.now(timezone.utc).replace(tzinfo=None)
        statement = insert(OtpConfigIp).values(
            [
                {"ip": ip, "otp_config_id": otp_config_id, "seen_at": seen_at}
                for ip, otp_config_id in pairs
            ]
        )
        statement = statement.on_conflict_do_update(
            constraint="uq_otp_config_ips_ip_config",
            set_={"seen_at": statement.excluded.seen_at},
        )

        with self._session_factory() as db:
            db.execute(statement)
            db.commit()
