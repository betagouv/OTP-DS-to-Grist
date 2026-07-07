"""
Tests unitaires pour app.py — fonction vite_asset
"""

import json
from unittest.mock import patch
from pathlib import Path

import pytest
from app import vite_asset, app


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
