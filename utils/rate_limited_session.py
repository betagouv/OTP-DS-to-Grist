import random
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils.log import log


class RateLimitedSession(requests.Session):
    """Session HTTP générique réagissant aux réponses 429.

    Sur une réponse 429, attend un délai puis relance la requête.
    Le délai est déterminé dans l'ordre :
      Retry-After     : secondes à attendre avant de relancer
      RateLimit-Reset : timestamp epoch (s) de fin de fenêtre (le plus fiable)
      fallback_delay  : valeur de repli si aucun en-tête n'est transmis

    Un délai aléatoire borné (max_random_delay) est ajouté pour disperser
    les relances (éviter l'effet thundering herd).
    """

    def __init__(
        self,
        max_retries: int = 3,
        fallback_delay: float = 60,
        max_random_delay: float = 5,
    ) -> None:
        super().__init__()
        self.max_retries = max(1, int(max_retries))
        self.fallback_delay = float(fallback_delay)
        self.max_random_delay = float(max_random_delay)

    def request(self, method, url, *args, **kwargs) -> requests.Response:
        for attempt in range(1, self.max_retries + 1):
            response = super().request(method, url, *args, **kwargs)
            if response.status_code != 429 or attempt == self.max_retries:
                return response
            delay = self._retry_delay(response)
            log(
                f"429 Too Many Requests - attente de {delay:.0f}s "
                f"avant nouvelle tentative (essai {attempt}/{self.max_retries - 1})"
            )
            time.sleep(delay)
        return response

    def _retry_delay(self, response: requests.Response) -> float:
        jitter = random.uniform(0, self.max_random_delay)
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            return float(retry_after) + jitter

        reset = response.headers.get("RateLimit-Reset")
        if reset is not None:
            return max(0.0, float(reset) - time.time()) + jitter

        return self.fallback_delay + jitter


def build_rate_limited_session(
    max_retries: int,
    fallback_delay: float,
    max_random_delay: float,
) -> RateLimitedSession:
    """Assemble une session prête à l'emploi : anti-429 + retry 5xx.

    L'anti-429 est porté par RateLimitedSession.request() (les trois
    paramètres max_retries / fallback_delay / max_random_delay). L'adapter
    monté ici ne traite que les erreurs serveur 5xx (total=3, backoff 1s,
    statuts [500, 502, 503, 504], raise_on_status=False).

    allowed_methods=None : aucun filtre sur les verbes → tous les verbes
    (le défaut urllib3 exclut précisément POST et PATCH).
    """
    session = RateLimitedSession(
        max_retries=max_retries,
        fallback_delay=fallback_delay,
        max_random_delay=max_random_delay,
    )

    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=None,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session