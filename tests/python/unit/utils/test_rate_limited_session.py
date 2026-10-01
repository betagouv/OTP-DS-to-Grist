from unittest.mock import MagicMock, patch

import requests

from utils.rate_limited_session import (
    RateLimitedSession,
    build_rate_limited_session,
)

DEFAULT_MAX_RETRIES = 3
DEFAULT_FALLBACK_DELAY = 60
DEFAULT_MAX_RANDOM_DELAY = 5


def _mock_response(status_code=200, json_data=None, headers=None):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data or {}
    response.headers = headers or {}
    return response


class TestRetryDelay:
    """Tests pour RateLimitedSession._retry_delay"""

    def _session(self):
        return RateLimitedSession(
            max_retries=DEFAULT_MAX_RETRIES,
            fallback_delay=DEFAULT_FALLBACK_DELAY,
            max_random_delay=DEFAULT_MAX_RANDOM_DELAY,
        )

    def test_retry_after_header_used(self):
        """Retry-After présent → le délai est son nombre de secondes"""
        session = self._session()

        with patch("random.uniform", return_value=0):
            assert session._retry_delay(_mock_response(429, headers={"Retry-After": "15"})) == 15.0

    def test_retry_after_takes_precedence_over_reset(self):
        """Retry-After présent → prioritaire sur RateLimit-Reset"""
        session = self._session()
        response = _mock_response(429, headers={"Retry-After": "10", "RateLimit-Reset": "9999999999"})

        with patch("random.uniform", return_value=0), patch("time.time", return_value=0):
            assert session._retry_delay(response) == 10.0

    def test_rate_limit_reset_used_when_no_retry_after(self):
        """Sans Retry-After → RateLimit-Reset moins l'heure courante"""
        session = self._session()

        with patch("random.uniform", return_value=0), patch("time.time", return_value=40):
            assert session._retry_delay(_mock_response(429, headers={"RateLimit-Reset": "100"})) == 60.0

    def test_reset_in_past_is_clamped_to_zero(self):
        """RateLimit-Reset déjà passé → délai écrasé à 0"""
        session = self._session()

        with patch("random.uniform", return_value=0), patch("time.time", return_value=100):
            assert session._retry_delay(_mock_response(429, headers={"RateLimit-Reset": "50"})) == 0.0

    def test_fallback_delay_when_no_headers(self):
        """Ni Retry-After ni RateLimit-Reset → délai de repli"""
        session = self._session()

        with patch("random.uniform", return_value=0):
            assert session._retry_delay(_mock_response(429)) == DEFAULT_FALLBACK_DELAY

    def test_jitter_is_uniform_and_bounded(self):
        """Un délai aléatoire borné est ajouté au délai du serveur"""
        session = self._session()

        with patch("random.uniform") as mock_uniform:
            mock_uniform.return_value = 3.5
            assert session._retry_delay(_mock_response(429, headers={"Retry-After": "10"})) == 13.5
            mock_uniform.assert_called_once_with(0, DEFAULT_MAX_RANDOM_DELAY)

    def test_custom_fallback_and_jitter_are_used(self):
        """fallback_delay et max_random_delay injectés pilotent le délai"""
        session = RateLimitedSession(
            max_retries=1, fallback_delay=123, max_random_delay=2
        )

        with patch("random.uniform", return_value=1.5):
            assert session._retry_delay(_mock_response(429)) == 124.5


class TestRateLimitedSession:
    """Tests pour le comportement 429 de RateLimitedSession"""

    def _session(self):
        return RateLimitedSession(
            max_retries=DEFAULT_MAX_RETRIES,
            fallback_delay=DEFAULT_FALLBACK_DELAY,
            max_random_delay=DEFAULT_MAX_RANDOM_DELAY,
        )

    @patch.object(requests.Session, "request")
    @patch("utils.rate_limited_session.log")
    @patch("time.sleep")
    def test_non_429_returned_immediately(self, mock_sleep, mock_log, mock_request):
        """Réponse non-429 → renvoyée telle quelle, sans attente ni log"""
        mock_request.return_value = _mock_response(200)

        response = self._session().request("POST", "http://dn")

        assert response.status_code == 200
        mock_request.assert_called_once_with("POST", "http://dn")
        mock_sleep.assert_not_called()
        mock_log.assert_not_called()

    @patch.object(requests.Session, "request")
    @patch("utils.rate_limited_session.log")
    @patch("time.sleep")
    def test_success_on_second_attempt(self, mock_sleep, mock_log, mock_request):
        """429 puis 200 → le délai est attendu puis la requête est relancée"""
        mock_request.side_effect = [
            _mock_response(429, headers={"Retry-After": "10"}),
            _mock_response(200),
        ]

        with patch("random.uniform", return_value=0):
            response = self._session().request("POST", "http://dn")

        assert response.status_code == 200
        assert mock_request.call_count == 2
        mock_sleep.assert_called_once_with(10.0)

    @patch.object(requests.Session, "request")
    @patch("utils.rate_limited_session.log")
    @patch("time.sleep")
    def test_log_mentions_429_and_delay(self, mock_sleep, mock_log, mock_request):
        """Le log mentionne le 429 et le délai d'attente"""
        mock_request.side_effect = [
            _mock_response(429, headers={"Retry-After": "10"}),
            _mock_response(200),
        ]

        with patch("random.uniform", return_value=0):
            self._session().request("POST", "http://dn")

        assert mock_log.call_count == 1
        message = mock_log.call_args[0][0]
        assert "429" in message
        assert "10" in message

    @patch.object(requests.Session, "request")
    @patch("utils.rate_limited_session.log")
    @patch("time.sleep")
    def test_exhaustion_returns_429(self, mock_sleep, mock_log, mock_request):
        """Essais épuisés → la dernière réponse 429 remonte"""
        mock_request.side_effect = [
            _mock_response(429, headers={"Retry-After": "10"}),
            _mock_response(429, headers={"Retry-After": "10"}),
            _mock_response(429, headers={"Retry-After": "10"}),
        ]

        with patch("random.uniform", return_value=0):
            response = self._session().request("POST", "http://dn")

        assert response.status_code == 429
        assert mock_request.call_count == DEFAULT_MAX_RETRIES
        assert mock_sleep.call_count == DEFAULT_MAX_RETRIES - 1
        assert mock_log.call_count == DEFAULT_MAX_RETRIES - 1

    @patch.object(requests.Session, "request")
    @patch("utils.rate_limited_session.log")
    @patch("time.sleep")
    def test_custom_max_retries_are_honored(self, mock_sleep, mock_log, mock_request):
        """max_retries injecté borne le nombre de tentatives"""
        mock_request.side_effect = [_mock_response(429) for _ in range(5)]

        with patch("random.uniform", return_value=0):
            response = RateLimitedSession(
                max_retries=5, fallback_delay=5, max_random_delay=0
            ).request("POST", "http://dn")

        assert response.status_code == 429
        assert mock_request.call_count == 5
        assert mock_sleep.call_count == 4

    @patch.object(requests.Session, "request")
    @patch("utils.rate_limited_session.log")
    @patch("time.sleep")
    def test_5xx_returned_without_retry(self, mock_sleep, mock_log, mock_request):
        """5xx → renvoyé sans relance (géré par l'adapter urllib3)"""
        mock_request.return_value = _mock_response(500)

        response = self._session().request("POST", "http://dn")

        assert response.status_code == 500
        mock_request.assert_called_once()
        mock_sleep.assert_not_called()
        mock_log.assert_not_called()

    @patch.object(requests.Session, "request")
    @patch("utils.rate_limited_session.log")
    @patch("time.sleep")
    def test_get_verb_uses_same_protection(self, mock_sleep, mock_log, mock_request):
        """Le verbe GET passe par le même mécanisme anti-429"""
        mock_request.side_effect = [
            _mock_response(429, headers={"Retry-After": "5"}),
            _mock_response(200),
        ]

        with patch("random.uniform", return_value=0):
            response = self._session().get("http://dn")

        assert response.status_code == 200
        assert mock_request.call_count == 2
        mock_sleep.assert_called_once_with(5.0)


class TestBuildRateLimitedSession:
    """Tests pour build_rate_limited_session (assemblage de la session complète)"""

    def _built_session(self):
        return build_rate_limited_session(
            max_retries=DEFAULT_MAX_RETRIES,
            fallback_delay=DEFAULT_FALLBACK_DELAY,
            max_random_delay=DEFAULT_MAX_RANDOM_DELAY,
        )

    def test_returns_rate_limited_session_parameterized(self):
        """La session assemblée est un RateLimitedSession paramétré aux valeurs passées"""
        session = self._built_session()

        assert isinstance(session, RateLimitedSession)
        assert session.max_retries == DEFAULT_MAX_RETRIES
        assert session.fallback_delay == DEFAULT_FALLBACK_DELAY
        assert session.max_random_delay == DEFAULT_MAX_RANDOM_DELAY

    def test_mounts_same_retry_adapter_on_https_and_http(self):
        """Un adapter retry 5xx (total=3, backoff 1, 500/502/503/504) monte sur https et http"""
        session = self._built_session()

        https_adapter = session.get_adapter("https://grist.example.com")
        http_adapter = session.get_adapter("http://grist.example.com")
        assert https_adapter is http_adapter
        assert https_adapter.max_retries.total == 3
        assert https_adapter.max_retries.backoff_factor == 1
        assert https_adapter.max_retries.status_forcelist == [500, 502, 503, 504]
        assert https_adapter.max_retries.raise_on_status is False

    def test_all_methods_allowed(self):
        """allowed_methods est None → tous les verbes sont retryables (incl. POST/PATCH)"""
        retries = (
            self._built_session()
            .get_adapter("https://grist.example.com")
            .max_retries
        )

        assert retries.allowed_methods is None
        assert retries._is_method_retryable("GET") is True
        assert retries._is_method_retryable("POST") is True
        assert retries._is_method_retryable("PATCH") is True