import datetime as dt
from unittest.mock import MagicMock, patch

import pytest
import requests

from grist.service_account import (
    ResolvedGristKey,
    ServiceAccountsNotEnabledError,
    is_service_account_email,
    resolve_grist_api_key,
    service_account_expires_at,
)


class TestIsServiceAccountEmail:
    """Tests unitaires pour is_service_account_email"""

    def test_service_account_tld(self):
        assert is_service_account_email("sa-1@serviceaccounts.invalid")

    def test_regular_user_email(self):
        assert not is_service_account_email("user@example.com")

    def test_missing_email(self):
        assert not is_service_account_email(None)

    def test_case_insensitive(self):
        assert is_service_account_email("SA-1@SERVICEACCOUNTS.INVALID")


class TestServiceAccountExpiresAt:
    """Tests unitaires pour service_account_expires_at"""

    def test_same_month_next_year_first_day(self):
        """2026-11-26 -> 2027-11-01 (premier jour du même mois, an + 1)"""
        assert (
            service_account_expires_at(dt.date(2026, 11, 26))
            == "2027-11-01T00:00:00.000Z"
        )

    def test_end_of_month(self):
        """2026-12-31 -> 2027-12-01"""
        assert (
            service_account_expires_at(dt.date(2026, 12, 31))
            == "2027-12-01T00:00:00.000Z"
        )

    def test_leap_day(self):
        """2028-02-29 -> 2029-02-01 (pas de calcul sur le jour du mois)"""
        assert (
            service_account_expires_at(dt.date(2028, 2, 29))
            == "2029-02-01T00:00:00.000Z"
        )

    def test_defaults_to_today(self):
        today = dt.date.today()
        expected = dt.date(today.year + 1, today.month, 1)
        assert service_account_expires_at() == f"{expected.isoformat()}T00:00:00.000Z"


def _http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(response=response)


class TestResolveGristApiKey:
    """Tests unitaires pour resolve_grist_api_key"""

    def _client(self, email: str | None) -> MagicMock:
        client = MagicMock()
        client.get_profile.return_value = {"email": email}
        return client

    def test_service_account_key_returned_as_is(self):
        """Clé de compte de service -> telle quelle, aucune création."""
        client = self._client("sa-1@serviceaccounts.invalid")
        with (
            patch("grist.service_account.GristClient", return_value=client),
            patch("grist.service_account.require_owner_access") as mock_owner,
        ):
            result = resolve_grist_api_key("https://grist.test", "sa-key", "doc123")

        assert result == ResolvedGristKey(
            "sa-key", "sa-1@serviceaccounts.invalid", False
        )
        mock_owner.assert_not_called()
        client.create_service_account.assert_not_called()

    def test_user_key_creates_service_account_and_grants_owner(self):
        """Clé utilisateur owner -> compte de service créé, attaché en owners."""
        client = self._client("user@example.com")
        client.create_service_account.return_value = {
            "login": "sa-7@serviceaccounts.invalid",
            "key": "key-sa-7",
        }
        with (
            patch("grist.service_account.GristClient", return_value=client),
            patch("grist.service_account.require_owner_access"),
        ):
            result = resolve_grist_api_key("https://grist.test", "user-key", "doc123")

        assert result.api_key == "key-sa-7"
        assert result.owner_email == "user@example.com"
        assert result.service_account_created

        label, description, expires_at = client.create_service_account.call_args.args
        assert label == "OTP-DS-to-Grist — user@example.com"
        assert "doc123" in description
        assert expires_at == service_account_expires_at(dt.date.today())
        client.update_doc_access.assert_called_once_with(
            {"sa-7@serviceaccounts.invalid": "owners"}
        )

    def test_user_key_requires_owner_access_before_creating(self):
        """Sans accès owners, aucun compte de service n'est créé."""
        client = self._client("user@example.com")
        with (
            patch("grist.service_account.GristClient", return_value=client),
            patch("grist.service_account.require_owner_access") as mock_owner,
        ):
            mock_owner.side_effect = RuntimeError("pas owners")
            with pytest.raises(RuntimeError, match="pas owners"):
                resolve_grist_api_key("https://grist.test", "user-key", "doc123")

        client.create_service_account.assert_not_called()

    def test_service_accounts_not_enabled_raises_clear_error(self):
        """404 sur /service-accounts -> erreur explicite, non relancée en HTTPError."""
        client = self._client("user@example.com")
        client.create_service_account.side_effect = _http_error(404)
        with (
            patch("grist.service_account.GristClient", return_value=client),
            patch("grist.service_account.require_owner_access"),
            pytest.raises(
                ServiceAccountsNotEnabledError, match="GRIST_ENABLE_SERVICE_ACCOUNTS"
            ),
        ):
            resolve_grist_api_key("https://grist.test", "user-key", "doc123")

    def test_other_http_error_is_reraised(self):
        """Une erreur HTTP autre que 404 n'est pas traduite."""
        client = self._client("user@example.com")
        client.create_service_account.side_effect = _http_error(500)
        with (
            patch("grist.service_account.GristClient", return_value=client),
            patch("grist.service_account.require_owner_access"),
            pytest.raises(requests.HTTPError),
        ):
            resolve_grist_api_key("https://grist.test", "user-key", "doc123")
