from unittest.mock import patch

from sync.preflight import verify_api_connections


class TestVerifyApiConnections:
    """Tests pour verify_api_connections"""

    @patch("sync.preflight.test_demarches_api")
    @patch("sync.preflight.test_grist_api")
    def test_both_success(self, mock_grist, mock_demarches):
        """Test avec succès des deux APIs"""
        mock_demarches.return_value = (True, "DS OK", "Titre démarche")
        mock_grist.return_value = (True, "Grist OK")

        success, results = verify_api_connections(
            "ds-token", "123", "https://grist.example.com", "grist-key", "doc123"
        )

        assert success is True
        assert len(results) == 2
        assert results[0]["type"] == "demarches"
        assert results[0]["success"] is True
        assert results[1]["type"] == "grist"
        assert results[1]["success"] is True

    @patch("sync.preflight.test_demarches_api")
    @patch("sync.preflight.test_grist_api")
    def test_partial_failure(self, mock_grist, mock_demarches):
        """Test avec échec partiel"""
        mock_demarches.return_value = (True, "DS OK", "Titre démarche")
        mock_grist.return_value = (False, "Grist Error")

        success, results = verify_api_connections(
            "ds-token", "123", "https://grist.example.com", "grist-key", "doc123"
        )

        assert success is False
        assert results[0]["success"] is True
        assert results[1]["success"] is False

    @patch("sync.preflight.test_demarches_api")
    @patch("sync.preflight.test_grist_api")
    def test_both_failure(self, mock_grist, mock_demarches):
        """Test avec échec des deux APIs"""
        mock_demarches.return_value = (False, "DS Error", None)
        mock_grist.return_value = (False, "Grist Error")

        success, results = verify_api_connections(
            "ds-token", "123", "https://grist.example.com", "grist-key", "doc123"
        )

        assert success is False
        assert all(not r["success"] for r in results)

    @patch("sync.preflight.test_demarches_api")
    @patch("sync.preflight.test_grist_api")
    def test_calls_with_correct_params(self, mock_grist, mock_demarches):
        """Test que les fonctions sont appelées avec les bons paramètres"""
        mock_demarches.return_value = (True, "DS OK", "Titre démarche")
        mock_grist.return_value = (True, "Grist OK")

        verify_api_connections(
            "ds-token", "123", "https://grist.example.com", "grist-key", "doc123"
        )

        mock_demarches.assert_called_once_with("ds-token", "123")
        mock_grist.assert_called_once_with(
            "https://grist.example.com", "grist-key", "doc123"
        )
