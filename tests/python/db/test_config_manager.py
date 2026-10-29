from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Engine, text

from configuration.config_manager import ConfigManager, ConfigNotFoundError

USER_ID = "userA"
DOC_ID = "docA"
GRIST_USER_EMAIL = "user@example.com"


def _new_config(**overrides) -> dict:
    config = {
        "ds_api_token": "ds-token",
        "demarche_number": "123",
        "grist_base_url": "https://grist.example.com/api",
        "grist_api_key": "grist-key",
        "grist_doc_id": DOC_ID,
        "grist_user_id": USER_ID,
        "filter_statuses": "en_construction",
    }

    return {**config, **overrides}


def _stored_tokens(engine: Engine, otp_config_id: int) -> tuple[str, str]:
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT ds_api_token, grist_api_key FROM otp_configurations "
                "WHERE id = :id"
            ),
            {"id": otp_config_id},
        ).one()

    return row.ds_api_token, row.grist_api_key


@pytest.fixture
def grist_client() -> Iterator[MagicMock]:
    """
    Client Grist simulé : save_config interroge Grist pour l'email, seule la
    base doit être réelle dans ces tests.
    """
    with patch("configuration.config_manager.GristClient") as client_class:
        client_class.return_value.get_grist_user_email.return_value = GRIST_USER_EMAIL

        yield client_class


@pytest.fixture
def config_manager(
    initialized_database, database_url, encryption_key, grist_client
) -> ConfigManager:
    return ConfigManager(database_url)


class TestSaveConfig:
    """Création et mise à jour d'une configuration sur une vraie base"""

    def test_created_config_is_loaded_back(self, config_manager):
        otp_config_id = config_manager.save_config(_new_config())

        config = config_manager.load_config_by_id(otp_config_id)

        assert config["otp_config_id"] == otp_config_id
        assert config["ds_api_token"] == "ds-token"
        assert config["grist_api_key"] == "grist-key"
        assert config["demarche_number"] == "123"
        assert config["filter_statuses"] == "en_construction"

    def test_tokens_are_stored_encrypted(self, config_manager, initialized_database):
        otp_config_id = config_manager.save_config(_new_config())

        ds_api_token, grist_api_key = _stored_tokens(
            initialized_database, otp_config_id
        )

        assert ds_api_token != "ds-token"
        assert grist_api_key != "grist-key"
        assert ConfigManager.decrypt_value(ds_api_token) == "ds-token"
        assert ConfigManager.decrypt_value(grist_api_key) == "grist-key"

    def test_grist_user_email_is_stored(self, config_manager, initialized_database):
        otp_config_id = config_manager.save_config(_new_config())

        with initialized_database.connect() as connection:
            email = connection.execute(
                text("SELECT grist_user_email FROM otp_configurations WHERE id = :id"),
                {"id": otp_config_id},
            ).scalar_one()

        assert email == GRIST_USER_EMAIL

    def test_update_with_empty_tokens_keeps_existing_ones(self, config_manager):
        otp_config_id = config_manager.save_config(_new_config())

        config_manager.save_config(
            _new_config(
                otp_config_id=otp_config_id,
                ds_api_token="",
                grist_api_key="",
                demarche_number="456",
            )
        )
        config = config_manager.load_config_by_id(otp_config_id)

        assert config["demarche_number"] == "456"
        assert config["ds_api_token"] == "ds-token"
        assert config["grist_api_key"] == "grist-key"

    def test_update_of_unknown_config_raises(self, config_manager):
        with pytest.raises(ConfigNotFoundError):
            config_manager.save_config(_new_config(otp_config_id=999))


class TestMultiConfig:
    """Plusieurs démarches pour un même utilisateur et un même document Grist"""

    def test_second_demarche_inherits_grist_api_key(self, config_manager):
        config_manager.save_config(_new_config(demarche_number="123"))

        second_id = config_manager.save_config(
            _new_config(demarche_number="456", grist_api_key="")
        )

        assert config_manager.load_config_by_id(second_id)["grist_api_key"] == (
            "grist-key"
        )

    def test_load_config_returns_every_demarche_of_the_document(self, config_manager):
        config_manager.save_config(_new_config(demarche_number="123"))
        config_manager.save_config(_new_config(demarche_number="456"))
        config_manager.save_config(
            _new_config(demarche_number="789", grist_doc_id="otherDoc")
        )

        configs = config_manager.load_config(USER_ID, DOC_ID)

        assert sorted(config["demarche_number"] for config in configs) == [
            "123",
            "456",
        ]


class TestLoadConfig:
    """Lecture des configurations absentes"""

    def test_load_by_unknown_id_raises(self, config_manager):
        with pytest.raises(ConfigNotFoundError):
            config_manager.load_config_by_id(999)

    def test_load_without_config_returns_single_empty_config(self, config_manager):
        configs = config_manager.load_config(USER_ID, DOC_ID)

        assert len(configs) == 1
        assert configs[0]["otp_config_id"] is None
        assert configs[0]["demarche_number"] == ""
