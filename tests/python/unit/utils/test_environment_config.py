import os
from utils.environment_config import build_environment


class TestBuildEnvironment:
    def test_filter_date_start(self):
        config = {"filter_date_start": "2024-01-01"}
        env = build_environment(config)
        assert env["DATE_DEPOT_DEBUT"] == "2024-01-01"

    def test_filter_date_end(self):
        config = {"filter_date_end": "2024-12-31"}
        env = build_environment(config)
        assert env["DATE_DEPOT_FIN"] == "2024-12-31"

    def test_filter_statuses(self):
        config = {"filter_statuses": "en_construction,en_instruction"}
        env = build_environment(config)
        assert env["STATUTS_DOSSIERS"] == "en_construction,en_instruction"

    def test_filter_groups(self):
        config = {"filter_groups": "1,2,3"}
        env = build_environment(config)
        assert env["GROUPES_INSTRUCTEURS"] == "1,2,3"

    def test_mapping_ds_api_token(self):
        config = {"ds_api_token": "abc123"}
        env = build_environment(config)
        assert env["DEMARCHES_API_TOKEN"] == "abc123"

    def test_mapping_demarche_number(self):
        config = {"demarche_number": "12345"}
        env = build_environment(config)
        assert env["DEMARCHE_NUMBER"] == "12345"

    def test_mapping_grist_base_url(self):
        config = {"grist_base_url": "https://grist.example.com"}
        env = build_environment(config)
        assert env["GRIST_BASE_URL"] == "https://grist.example.com"

    def test_mapping_grist_api_key(self):
        config = {"grist_api_key": "my_api_key"}
        env = build_environment(config)
        assert env["GRIST_API_KEY"] == "my_api_key"

    def test_mapping_grist_doc_id(self):
        config = {"grist_doc_id": "doc_123"}
        env = build_environment(config)
        assert env["GRIST_DOC_ID"] == "doc_123"

    def test_mapping_grist_user_id(self):
        config = {"grist_user_id": "user_456"}
        env = build_environment(config)
        assert env["GRIST_USER_ID"] == "user_456"

    def test_config_complete(self):
        config = {
            "ds_api_token": "token123",
            "demarche_number": "999",
            "grist_base_url": "https://grist.com",
            "grist_api_key": "key",
            "grist_doc_id": "doc",
            "grist_user_id": "user",
            "filter_date_start": "2024-01-01",
            "filter_date_end": "2024-12-31",
            "filter_statuses": "a,b",
            "filter_groups": "1,2",
        }
        env = build_environment(config)
        assert env["DEMARCHES_API_TOKEN"] == "token123"
        assert env["DEMARCHE_NUMBER"] == "999"
        assert env["GRIST_BASE_URL"] == "https://grist.com"
        assert env["GRIST_API_KEY"] == "key"
        assert env["GRIST_DOC_ID"] == "doc"
        assert env["GRIST_USER_ID"] == "user"
        assert env["DATE_DEPOT_DEBUT"] == "2024-01-01"
        assert env["DATE_DEPOT_FIN"] == "2024-12-31"
        assert env["STATUTS_DOSSIERS"] == "a,b"
        assert env["GROUPES_INSTRUCTEURS"] == "1,2"

    def test_config_empty(self):
        config = {}
        env = build_environment(config)
        # Les clés du mapping ne doivent pas être présentes
        assert "DEMARCHES_API_TOKEN" not in env
        assert "DEMARCHE_NUMBER" not in env
        # Mais l'environnement de base doit être présent
        assert "PATH" in env
