import pytest

from tests.python.db.runner import build_test_database_url


class TestBuildTestDatabaseUrl:
    """Dérivation de l'URL de test depuis l'URL du service `db` (sans base réelle)"""

    def test_appends_test_suffix_to_database_name(self):
        url = build_test_database_url("postgresql://user:secret@db:5432/otp_ds")

        assert url == "postgresql://user:secret@db:5432/otp_ds_test"

    def test_keeps_url_already_targeting_test_database(self):
        url = build_test_database_url("postgresql://user@localhost:5433/otp_ds_test")

        assert url == "postgresql://user@localhost:5433/otp_ds_test"

    def test_raises_when_url_has_no_database_name(self):
        with pytest.raises(ValueError):
            build_test_database_url("postgresql://user@localhost:5433")
