"""
Tests unitaires pour app.py — fonctions pures (vite_asset, get_available_groups)
"""

import json
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest
from app import vite_asset, get_available_groups, app


class TestViteAsset:
    """Tests pour la fonction vite_asset"""

    def test_debug_mode_default_entry(self):
        """Mode DEBUG : entry par défaut"""
        with patch.dict(app.config, {"DEBUG": True}):
            result = vite_asset()
        assert result == {
            "js": "http://localhost:5173/src/main.js",
            "css": None
        }

    def test_debug_mode_custom_entry(self):
        """Mode DEBUG : entry personnalisée"""
        with patch.dict(app.config, {"DEBUG": True}):
            result = vite_asset("src/other.js")
        assert result == {
            "js": "http://localhost:5173/src/other.js",
            "css": None,
        }

    @patch("app.url_for")
    def test_production_with_css(self, mock_url_for):
        """Mode production avec CSS dans le manifest"""
        mock_url_for.side_effect = lambda _, filename: f"/{filename}"
        manifest = {
            "src/main.js": {
                "file": "assets/main-DAw_rkyR.js",
                "css": ["assets/main-Cc52_ki1.css"],
            }
        }
        with patch.dict(app.config, {"DEBUG": False}):
            with patch.object(
                Path,
                "read_text",
                return_value=json.dumps(manifest)
            ):
                result = vite_asset()

        assert result == {
            "js": "/dist/assets/main-DAw_rkyR.js",
            "css": "/dist/assets/main-Cc52_ki1.css",
        }

    @patch("app.url_for")
    def test_production_without_css(self, mock_url_for):
        """Mode production sans CSS dans le manifest"""
        mock_url_for.side_effect = lambda _, filename: f"/{filename}"
        manifest = {
            "src/main.js": {
                "file": "assets/main-DAw_rkyR.js",
                "css": [],
            }
        }
        with patch.dict(app.config, {"DEBUG": False}):
            with patch.object(
                Path,
                "read_text",
                return_value=json.dumps(manifest)
            ):
                result = vite_asset()

        assert result == {
            "js": "/dist/assets/main-DAw_rkyR.js",
            "css": None,
        }

    @patch("app.url_for")
    def test_production_missing_entry(self, _):
        """Mode production : entry absente du manifest → KeyError"""
        manifest = {"src/main.js": {"file": "assets/main.js"}}
        with patch.dict(app.config, {"DEBUG": False}):
            with patch.object(
                Path,
                "read_text",
                return_value=json.dumps(manifest)
            ):
                    with pytest.raises(KeyError):
                        vite_asset("src/nonexistent.js")


class TestGetAvailableGroups:
    """Tests pour get_available_groups"""

    def test_missing_api_token_returns_empty(self):
        """Token manquant → retourne []"""
        assert get_available_groups(None, "123") == []
        assert get_available_groups("", "123") == []

    def test_missing_demarche_number_returns_empty(self):
        """Numéro de démarche manquant → retourne []"""
        assert get_available_groups("token", None) == []
        assert get_available_groups("token", "") == []

    @patch("queries_graphql.get_session_with_retries")
    def test_success_returns_groups(self, mock_session_factory):
        """Appel réussi → retourne liste de tuples (number, label)"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "demarche": {
                    "groupeInstructeurs": [
                        {"number": 1, "label": "Groupe A"},
                        {"number": 2, "label": "Groupe B"},
                    ]
                }
            }
        }
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_factory.return_value = mock_session

        result = get_available_groups("token123", "456")

        assert result == [(1, "Groupe A"), (2, "Groupe B")]
        mock_session.post.assert_called_once()

    @patch("queries_graphql.get_session_with_retries")
    def test_api_error_status_returns_empty(self, mock_session_factory):
        """Statut HTTP != 200 → retourne []"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_factory.return_value = mock_session

        assert get_available_groups("token", "123") == []

    @patch("queries_graphql.get_session_with_retries")
    def test_graphql_errors_returns_empty(self, mock_session_factory):
        """Erreurs GraphQL dans la réponse → retourne []"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errors": [{"message": "Unauthorized"}]}
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_factory.return_value = mock_session

        assert get_available_groups("token", "123") == []

    @patch("queries_graphql.get_session_with_retries")
    def test_empty_demarche_returns_empty(self, mock_session_factory):
        """Démarche sans groupe instructeur → retourne []"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"demarche": {"groupeInstructeurs": []}}
        }
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_factory.return_value = mock_session

        assert get_available_groups("token", "123") == []

    @patch("queries_graphql.get_session_with_retries", side_effect=Exception("Network error"))
    def test_exception_returns_empty(self, mock_session_factory):
        """Exception quelconque → retourne []"""
        assert get_available_groups("token", "123") == []
