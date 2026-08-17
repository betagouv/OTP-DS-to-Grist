"""
Tests unitaires pour dn/queries.py
"""

from unittest.mock import MagicMock, patch

import pytest

from dn.queries import get_available_groups


def _mock_session(mock_response):
    """Crée un mock de session avec post() qui retourne mock_response."""
    session = MagicMock()
    session.post.return_value = mock_response
    session.get.return_value = mock_response
    return session


# ============================================================
# get_demarche_dossiers_filtered
# ============================================================


class TestGetDemarcheDossiersFiltered:
    """Tests pour get_demarche_dossiers_filtered"""

    @patch("dn.queries.API_TOKEN", "")
    def test_no_token_raises(self):
        """Pas de token → ValueError"""
        from dn.queries import get_demarche_dossiers_filtered

        with pytest.raises(ValueError, match="token"):
            get_demarche_dossiers_filtered(123)

    @patch("dn.queries.get_session_with_retries")
    @patch("dn.queries.API_TOKEN", "test-token")
    def test_no_filters_returns_all(self, mock_session_factory):
        """Aucun filtre → retourne tous les dossiers"""
        from dn.queries import get_demarche_dossiers_filtered

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "demarche": {
                    "dossiers": {
                        "pageInfo": {"hasNextPage": False, "endCursor": "abc"},
                        "nodes": [
                            {"number": 1, "state": "en_construction"},
                            {"number": 2, "state": "accepte"},
                        ],
                    }
                }
            }
        }
        mock_session_factory.return_value = _mock_session(mock_response)

        result = get_demarche_dossiers_filtered(123)

        assert len(result) == 2
        assert result[0]["number"] == 1

    @patch("dn.queries.get_session_with_retries")
    @patch("dn.queries.API_TOKEN", "test-token")
    def test_date_debut_sent_as_server_filter(self, mock_session_factory):
        """date_debut → envoyé comme createdSince côté serveur"""
        from dn.queries import get_demarche_dossiers_filtered

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "demarche": {
                    "dossiers": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [{"number": 1, "state": "en_construction"}],
                    }
                }
            }
        }
        session = _mock_session(mock_response)
        mock_session_factory.return_value = session

        get_demarche_dossiers_filtered(123, date_debut="2024-01-15")

        call_args = session.post.call_args
        variables = call_args[1]["json"]["variables"]
        assert variables["createdSince"] == "2024-01-15T00:00:00Z"

    @patch("dn.queries.get_session_with_retries")
    @patch("dn.queries.API_TOKEN", "test-token")
    def test_date_fin_filters_client_side(self, mock_session_factory):
        """date_fin → filtrage côté client par dateDepot"""
        from dn.queries import get_demarche_dossiers_filtered

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "demarche": {
                    "dossiers": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [
                            {"number": 1, "state": "en_construction", "dateDepot": "2024-01-10T10:00:00Z"},
                            {"number": 2, "state": "accepte", "dateDepot": "2024-03-20T10:00:00Z"},
                        ],
                    }
                }
            }
        }
        mock_session_factory.return_value = _mock_session(mock_response)

        result = get_demarche_dossiers_filtered(123, date_fin="2024-02-01")

        assert len(result) == 1
        assert result[0]["number"] == 1

    @patch("dn.queries.get_session_with_retries")
    @patch("dn.queries.API_TOKEN", "test-token")
    def test_statuts_filters_client_side(self, mock_session_factory):
        """statuts → filtrage côté client par state"""
        from dn.queries import get_demarche_dossiers_filtered

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "demarche": {
                    "dossiers": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [
                            {"number": 1, "state": "en_construction", "dateDepot": "2024-01-10T10:00:00Z", "groupeInstructeur": {"number": "1", "id": "gid-1"}},
                            {"number": 2, "state": "accepte", "dateDepot": "2024-01-15T10:00:00Z", "groupeInstructeur": {"number": "2", "id": "gid-2"}},
                            {"number": 3, "state": "refuse", "dateDepot": "2024-01-20T10:00:00Z", "groupeInstructeur": {"number": "3", "id": "gid-3"}},
                        ],
                    }
                }
            }
        }
        mock_session_factory.return_value = _mock_session(mock_response)

        result = get_demarche_dossiers_filtered(123, statuts=["accepte"])

        assert len(result) == 1
        assert result[0]["number"] == 2

    @patch("dn.queries.get_session_with_retries")
    @patch("dn.queries.API_TOKEN", "test-token")
    def test_groupes_instructeurs_filters_client_side(self, mock_session_factory):
        """groupes_instructeurs → filtrage côté client par groupe.number"""
        from dn.queries import get_demarche_dossiers_filtered

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "demarche": {
                    "dossiers": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [
                            {"number": 1, "state": "en_construction", "dateDepot": "2024-01-10T10:00:00Z", "groupeInstructeur": {"number": "10", "id": "gid-10"}},
                            {"number": 2, "state": "en_construction", "dateDepot": "2024-01-15T10:00:00Z", "groupeInstructeur": {"number": "20", "id": "gid-20"}},
                        ],
                    }
                }
            }
        }
        mock_session_factory.return_value = _mock_session(mock_response)

        result = get_demarche_dossiers_filtered(123, groupes_instructeurs=["20"])

        assert len(result) == 1
        assert result[0]["number"] == 2

    @patch("dn.queries.get_session_with_retries")
    @patch("dn.queries.API_TOKEN", "test-token")
    def test_pagination_follows_next_page(self, mock_session_factory):
        """Pagination → suit hasNextPage"""
        from dn.queries import get_demarche_dossiers_filtered

        page1 = MagicMock()
        page1.status_code = 200
        page1.json.return_value = {
            "data": {
                "demarche": {
                    "dossiers": {
                        "pageInfo": {"hasNextPage": True, "endCursor": "cursor-2"},
                        "nodes": [{"number": 1, "state": "en_construction"}],
                    }
                }
            }
        }

        page2 = MagicMock()
        page2.status_code = 200
        page2.json.return_value = {
            "data": {
                "demarche": {
                    "dossiers": {
                        "pageInfo": {"hasNextPage": False, "endCursor": "cursor-3"},
                        "nodes": [{"number": 2, "state": "accepte"}],
                    }
                }
            }
        }

        session = MagicMock()
        session.post.side_effect = [page1, page2]
        mock_session_factory.return_value = session

        result = get_demarche_dossiers_filtered(123)

        assert len(result) == 2
        assert session.post.call_count == 2
        # Deuxième appel doit avoir le cursor
        second_call_vars = session.post.call_args_list[1][1]["json"]["variables"]
        assert second_call_vars["afterCursor"] == "cursor-2"


# ============================================================
# get_demarche
# ============================================================


class TestGetDemarche:
    """Tests pour get_demarche"""

    @patch("dn.queries.API_TOKEN", "")
    def test_no_token_raises(self):
        """Pas de token → ValueError"""
        from dn.queries import get_demarche

        with pytest.raises(ValueError, match="token"):
            get_demarche(123)

    @patch("dn.queries.get_session_with_retries")
    @patch("dn.queries.API_TOKEN", "test-token")
    def test_filters_out_header_and_explication_champs(self, mock_session_factory):
        """Filtre les HeaderSectionChamp et ExplicationChamp des dossiers"""
        from dn.queries import get_demarche

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "demarche": {
                    "dossiers": {
                        "nodes": [
                            {
                                "number": 1,
                                "champs": [
                                    {"__typename": "TextChamp", "label": "Nom"},
                                    {"__typename": "HeaderSectionChamp", "label": "Titre"},
                                    {"__typename": "ExplicationChamp", "label": "Info"},
                                ],
                                "annotations": [
                                    {"__typename": "TextChamp", "label": "Note"},
                                    {"__typename": "ExplicationChamp", "label": "Note info"},
                                ],
                            }
                        ]
                    }
                }
            }
        }
        mock_session_factory.return_value = _mock_session(mock_response)

        result = get_demarche(123)

        dossiers = result["dossiers"]["nodes"]
        assert len(dossiers[0]["champs"]) == 1
        assert dossiers[0]["champs"][0]["__typename"] == "TextChamp"
        assert len(dossiers[0]["annotations"]) == 1

    @patch("dn.queries.get_session_with_retries")
    @patch("dn.queries.API_TOKEN", "test-token")
    def test_permission_errors_ignored(self, mock_session_factory):
        """Erreurs de permission → ignorées, données retournées"""
        from dn.queries import get_demarche

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"demarche": {"dossiers": {"nodes": []}}},
            "errors": [{"message": "hidden due to permissions on field"}],
        }
        mock_session_factory.return_value = _mock_session(mock_response)

        result = get_demarche(123)
        assert "demarche" in result.get("data", {}) or "dossiers" in result

    @patch("dn.queries.get_session_with_retries")
    @patch("dn.queries.API_TOKEN", "test-token")
    def test_non_permission_errors_raise(self, mock_session_factory):
        """Erreurs non-permission → Exception"""
        from dn.queries import get_demarche

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": None,
            "errors": [{"message": "Could not fetch demarche"}],
        }
        mock_session_factory.return_value = _mock_session(mock_response)

        with pytest.raises(Exception, match="GraphQL errors"):
            get_demarche(123)

    @patch("dn.queries.get_session_with_retries")
    @patch("dn.queries.API_TOKEN", "test-token")
    def test_no_data_raises(self, mock_session_factory):
        """Pas de données retournées → Exception"""
        from dn.queries import get_demarche

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": None}
        mock_session_factory.return_value = _mock_session(mock_response)

        with pytest.raises(Exception, match="Aucune donnée"):
            get_demarche(123)


# ============================================================
# get_deleted_dossiers
# ============================================================


class TestGetDeletedDossiers:
    """Tests pour get_deleted_dossiers"""

    @patch("dn.queries.API_TOKEN", "")
    def test_no_token_raises(self):
        """Pas de token → ValueError"""
        from dn.queries import get_deleted_dossiers

        with pytest.raises(ValueError, match="token"):
            get_deleted_dossiers(123)

    @patch("dn.queries.get_session_with_retries")
    @patch("dn.queries.API_TOKEN", "test-token")
    def test_merges_deleted_and_pending(self, mock_session_factory):
        """Fusionne deletedDossiers + pendingDeletedDossiers"""
        from dn.queries import get_deleted_dossiers

        deleted_resp = MagicMock()
        deleted_resp.status_code = 200
        deleted_resp.json.return_value = {
            "data": {
                "demarche": {
                    "deletedDossiers": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [{"number": 10, "state": "supprime"}],
                    }
                }
            }
        }

        pending_resp = MagicMock()
        pending_resp.status_code = 200
        pending_resp.json.return_value = {
            "data": {
                "demarche": {
                    "pendingDeletedDossiers": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [{"number": 20, "state": "en_instruction"}],
                    }
                }
            }
        }

        session = MagicMock()
        session.post.side_effect = [deleted_resp, pending_resp]
        mock_session_factory.return_value = session

        result = get_deleted_dossiers(123)

        assert len(result) == 2
        assert result[0]["number"] == 10
        assert result[1]["number"] == 20

    @patch("dn.queries.get_session_with_retries")
    @patch("dn.queries.API_TOKEN", "test-token")
    def test_graphql_errors_raise(self, mock_session_factory):
        """Erreurs GraphQL → Exception"""
        from dn.queries import get_deleted_dossiers

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"demarche": {"deletedDossiers": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": []}}},
            "errors": [{"message": "Access denied"}],
        }
        mock_session_factory.return_value = _mock_session(mock_response)

        with pytest.raises(Exception, match="GraphQL errors"):
            get_deleted_dossiers(123)


# ============================================================
# get_demarche_dossiers_labels_only
# ============================================================


class TestGetDemarcheDossiersLabelsOnly:
    """Tests pour get_demarche_dossiers_labels_only"""

    @patch("dn.queries.API_TOKEN", "")
    def test_no_token_raises(self):
        """Pas de token → ValueError"""
        from dn.queries import get_demarche_dossiers_labels_only

        with pytest.raises(ValueError, match="token"):
            get_demarche_dossiers_labels_only(123)

    @patch("dn.queries.get_session_with_retries")
    @patch("dn.queries.API_TOKEN", "test-token")
    def test_returns_labels(self, mock_session_factory):
        """Retourne number + labels pour chaque dossier"""
        from dn.queries import get_demarche_dossiers_labels_only

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "demarche": {
                    "dossiers": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [
                            {"number": 1, "labels": [{"id": "l1", "name": "Urgent", "color": "red"}]},
                            {"number": 2, "labels": []},
                        ],
                    }
                }
            }
        }
        mock_session_factory.return_value = _mock_session(mock_response)

        result = get_demarche_dossiers_labels_only(123)

        assert len(result) == 2
        assert result[0]["labels"][0]["name"] == "Urgent"
        assert result[1]["labels"] == []

    @patch("dn.queries.get_session_with_retries")
    @patch("dn.queries.API_TOKEN", "test-token")
    def test_pagination(self, mock_session_factory):
        """Pagination → suit hasNextPage"""
        from dn.queries import get_demarche_dossiers_labels_only

        page1 = MagicMock()
        page1.status_code = 200
        page1.json.return_value = {
            "data": {
                "demarche": {
                    "dossiers": {
                        "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                        "nodes": [{"number": 1, "labels": []}],
                    }
                }
            }
        }

        page2 = MagicMock()
        page2.status_code = 200
        page2.json.return_value = {
            "data": {
                "demarche": {
                    "dossiers": {
                        "pageInfo": {"hasNextPage": False, "endCursor": "c2"},
                        "nodes": [{"number": 2, "labels": []}],
                    }
                }
            }
        }

        session = MagicMock()
        session.post.side_effect = [page1, page2]
        mock_session_factory.return_value = session

        result = get_demarche_dossiers_labels_only(123)

        assert len(result) == 2
        assert session.post.call_count == 2


# ============================================================
# get_dossier_geojson
# ============================================================


class TestGetDossierGeojson:
    """Tests pour get_dossier_geojson"""

    @patch("dn.queries.API_TOKEN", "")
    def test_no_token_raises(self):
        """Pas de token → ValueError"""
        from dn.queries import get_dossier_geojson

        with pytest.raises(ValueError, match="token"):
            get_dossier_geojson(123)

    @patch("dn.queries.get_session_with_retries")
    @patch("dn.queries.API_URL", "https://www.demarches-simplifiees.fr/api/v2/graphql")
    @patch("dn.queries.API_TOKEN", "test-token")
    def test_url_derivation(self, mock_session_factory):
        """Dérive l'URL GeoJSON en retirant /api/v2/graphql"""
        from dn.queries import get_dossier_geojson

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"type": "FeatureCollection", "features": []}
        mock_response.raise_for_status = MagicMock()
        session = _mock_session(mock_response)
        mock_session_factory.return_value = session

        get_dossier_geojson(456)

        call_args = session.get.call_args
        assert call_args[0][0] == "https://www.demarches-simplifiees.fr/dossiers/456/geojson"

    @patch("dn.queries.get_session_with_retries")
    @patch("dn.queries.API_URL", "https://www.demarches-simplifiees.fr/api/v2/graphql")
    @patch("dn.queries.API_TOKEN", "test-token")
    def test_returns_geojson(self, mock_session_factory):
        """Retourne le GeoJSON brut"""
        from dn.queries import get_dossier_geojson

        expected = {"type": "FeatureCollection", "features": [{"type": "Feature"}]}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected
        mock_response.raise_for_status = MagicMock()
        mock_session_factory.return_value = _mock_session(mock_response)

        result = get_dossier_geojson(456)

        assert result == expected


# ============================================================
# get_available_groups
# ============================================================


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

    @patch("dn.queries.get_session_with_retries")
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

    @patch("dn.queries.get_session_with_retries")
    def test_api_error_status_returns_empty(self, mock_session_factory):
        """Statut HTTP != 200 → retourne []"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_factory.return_value = mock_session

        assert get_available_groups("token", "123") == []

    @patch("dn.queries.get_session_with_retries")
    def test_graphql_errors_returns_empty(self, mock_session_factory):
        """Erreurs GraphQL dans la réponse → retourne []"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errors": [{"message": "Unauthorized"}]}
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_factory.return_value = mock_session

        assert get_available_groups("token", "123") == []

    @patch("dn.queries.get_session_with_retries")
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

    @patch("dn.queries.get_session_with_retries", side_effect=Exception("Network error"))
    def test_exception_returns_empty(self, mock_session_factory):
        """Exception quelconque → retourne []"""
        assert get_available_groups("token", "123") == []
