import pytest
from unittest.mock import MagicMock, patch

from dn.client import (
    get_deleted_dossiers,
    get_demarche,
    get_demarche_dossiers,
    get_demarche_dossiers_labels_only,
    get_dossier,
    get_groups,
    get_session_with_retries,
)


def _mock_response(status_code=200, json_data=None, headers=None):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data or {}
    response.headers = headers or {}
    return response


class TestGetGroups:
    """Tests pour get_groups"""

    def test_missing_api_token_returns_empty(self):
        """Token manquant → retourne []"""
        assert get_groups(None, "123") == []
        assert get_groups("", "123") == []

    def test_missing_demarche_number_returns_empty(self):
        """Numéro de démarche manquant → retourne []"""
        assert get_groups("token", None) == []
        assert get_groups("token", "") == []

    @patch("dn.client.get_session_with_retries")
    def test_success_returns_groups(self, mock_session_factory):
        """Appel réussi → retourne liste de tuples (number, label)"""
        mock_response = _mock_response(
            json_data={
                "data": {
                    "demarche": {
                        "groupeInstructeurs": [
                            {"number": 1, "label": "Groupe A"},
                            {"number": 2, "label": "Groupe B"},
                        ]
                    }
                }
            }
        )
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_factory.return_value = mock_session

        result = get_groups("token123", "456")

        assert result == [(1, "Groupe A"), (2, "Groupe B")]
        mock_session.post.assert_called_once()

    @patch("dn.client.get_session_with_retries")
    def test_api_error_status_returns_empty(self, mock_session_factory):
        """Statut HTTP != 200 → retourne []"""
        mock_response = _mock_response(status_code=401)
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_factory.return_value = mock_session

        assert get_groups("token", "123") == []

    @patch("dn.client.get_session_with_retries")
    def test_graphql_errors_returns_empty(self, mock_session_factory):
        """Erreurs GraphQL dans la réponse → retourne []"""
        mock_response = _mock_response(json_data={"errors": [{"message": "Unauthorized"}]})
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_factory.return_value = mock_session

        assert get_groups("token", "123") == []

    @patch("dn.client.get_session_with_retries")
    def test_empty_demarche_returns_empty(self, mock_session_factory):
        """Démarche sans groupe instructeur → retourne []"""
        mock_response = _mock_response(
            json_data={"data": {"demarche": {"groupeInstructeurs": []}}}
        )
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_factory.return_value = mock_session

        assert get_groups("token", "123") == []

    @patch("dn.client.get_session_with_retries", side_effect=Exception("Network error"))
    def test_exception_returns_empty(self, mock_session_factory):
        """Exception quelconque → retourne []"""
        assert get_groups("token", "123") == []

    @patch("dn.client.get_session_with_retries")
    def test_graphql_errors_are_logged(self, mock_session_factory, capsys):
        """Erreurs GraphQL → les messages sont loggés (concis, sans le dict brut)"""
        mock_response = _mock_response(json_data={"errors": [{"message": "Unauthorized"}]})
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_factory.return_value = mock_session

        get_groups("token", "123")

        output = capsys.readouterr().out
        assert "Unauthorized" in output
        assert "{'message'" not in output

    @patch("dn.client.get_session_with_retries", side_effect=Exception("Network error"))
    def test_exception_is_logged(self, mock_session_factory, capsys):
        """Exception → l'erreur est loggée avant de retourner []"""
        get_groups("token", "123")

        assert "Network error" in capsys.readouterr().out


class TestGetSessionWithRetries:
    """Tests pour get_session_with_retries (singleton)"""

    @patch("dn.client.HTTPAdapter")
    @patch("dn.client.RateLimitedSession")
    def test_reuses_same_session(self, mock_session_cls, mock_adapter_cls):
        """La session est un singleton : deux appels → même objet"""
        mock_session_cls.return_value = MagicMock()
        with patch("dn.client._session", None):
            session1 = get_session_with_retries()
            session2 = get_session_with_retries()

        assert session1 is session2
        assert mock_session_cls.call_count == 1

    @patch("dn.client.HTTPAdapter")
    @patch("dn.client.RateLimitedSession")
    def test_mounts_retry_adapter_on_https_and_http(self, mock_session_cls, mock_adapter_cls):
        """Un adapter avec retry est monté sur https:// et http://"""
        session = MagicMock()
        mock_session_cls.return_value = session
        with patch("dn.client._session", None):
            get_session_with_retries()

        assert mock_adapter_cls.call_count == 1
        assert session.mount.call_count == 2
        schemas = [call[0][0] for call in session.mount.call_args_list]
        assert schemas == ["https://", "http://"]


class TestGetDossier:
    """Tests pour get_dossier"""

    @patch("dn.client.API_TOKEN", "")
    def test_missing_token_raises_value_error(self):
        """Token API non configuré → ValueError"""
        with pytest.raises(ValueError):
            get_dossier(42)

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_success_filters_unwanted_champs(self, mock_session_factory):
        """Succès : HeaderSectionChamp/ExplicationChamp filtrés, session.post appelé"""
        raw_dossier = {
            "id": "Q2xpZW50LTE=",
            "number": 42,
            "champs": [
                {"id": "c1", "__typename": "TextChamp"},
                {"id": "c2", "__typename": "HeaderSectionChamp"},
            ],
            "annotations": [
                {"id": "a1", "__typename": "ExplicationChamp"},
                {"id": "a2", "__typename": "TextChamp"},
            ],
        }
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(
            json_data={"data": {"dossier": raw_dossier}}
        )
        mock_session_factory.return_value = mock_session

        result = get_dossier(42)

        assert result["number"] == 42
        assert result["champs"] == [{"id": "c1", "__typename": "TextChamp"}]
        assert result["annotations"] == [{"id": "a2", "__typename": "TextChamp"}]
        mock_session.post.assert_called_once()

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_permission_errors_are_ignored(self, mock_session_factory):
        """Erreurs de permission seules → continue le traitement"""
        raw_dossier = {"id": "Q2xpZW50LTE=", "number": 42, "champs": []}
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(
            json_data={
                "data": {"dossier": raw_dossier},
                "errors": [{"message": "Champs masqués pour cause de permissions"}],
            }
        )
        mock_session_factory.return_value = mock_session

        result = get_dossier(42)

        assert result["number"] == 42

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_non_permission_errors_raise(self, mock_session_factory):
        """Erreur GraphQL non liée aux permissions → Exception"""
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(
            json_data={
                "data": None,
                "errors": [{"message": "Dossier introuvable"}],
            }
        )
        mock_session_factory.return_value = mock_session

        with pytest.raises(Exception, match="Dossier introuvable"):
            get_dossier(42)

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_inaccessible_dossier_returns_empty_dict(self, mock_session_factory):
        """data.dossier absent (permissions) → retourne {}"""
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(json_data={"data": None})
        mock_session_factory.return_value = mock_session

        assert get_dossier(42) == {}


class TestGetDemarche:
    """Tests pour get_demarche"""

    @patch("dn.client.API_TOKEN", "")
    def test_missing_token_raises_value_error(self):
        """Token API non configuré → ValueError"""
        with pytest.raises(ValueError):
            get_demarche(7)

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_success_returns_demarche(self, mock_session_factory):
        """Succès : dossiers.nodes préservés, champs problématiques filtrés"""
        demarche = {
            "id": "RGVtYXJjaGUtMQ==",
            "number": 7,
            "title": "Ma démarche",
            "state": "publiee",
            "activeRevision": {
                "champDescriptors": [
                    {"id": "d1", "type": "TextChampDescriptor"},
                    {"id": "d2", "type": "HeaderSectionChamp"},
                ],
                "annotationDescriptors": [],
            },
            "dossiers": {
                "nodes": [
                    {
                        "number": 1,
                        "champs": [
                            {"id": "c1", "__typename": "TextChamp"},
                            {"id": "c2", "__typename": "ExplicationChamp"},
                        ],
                        "annotations": [],
                    }
                ]
            },
        }
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(
            json_data={"data": {"demarche": demarche}}
        )
        mock_session_factory.return_value = mock_session

        result = get_demarche(7)

        assert result["title"] == "Ma démarche"
        assert len(result["dossiers"]["nodes"]) == 1
        descriptors = result["activeRevision"]["champDescriptors"]
        assert descriptors == [{"id": "d1", "type": "TextChampDescriptor"}]
        champs = result["dossiers"]["nodes"][0]["champs"]
        assert champs == [{"id": "c1", "__typename": "TextChamp"}]

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_permission_errors_are_ignored(self, mock_session_factory):
        """Erreurs de permission seules → continue le traitement"""
        demarche = {
            "id": "RGVtYXJjaGUtMQ==",
            "number": 7,
            "title": "Ma démarche",
            "dossiers": {"nodes": []},
        }
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(
            json_data={
                "data": {"demarche": demarche},
                "errors": [
                    {"message": "objets masqués en raison de restrictions de permissions"}
                ],
            }
        )
        mock_session_factory.return_value = mock_session

        result = get_demarche(7)

        assert result["number"] == 7

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_missing_demarche_raises(self, mock_session_factory):
        """data.demarche absent → Exception"""
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(json_data={"data": None})
        mock_session_factory.return_value = mock_session

        with pytest.raises(Exception, match="Aucune donnée de démarche"):
            get_demarche(7)


class TestGetDemarcheDossiers:
    """Tests pour get_demarche_dossiers"""

    @patch("dn.client.API_TOKEN", "")
    def test_missing_token_raises_value_error(self):
        """Token API non configuré → ValueError"""
        with pytest.raises(ValueError):
            get_demarche_dossiers(7)

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_no_filter_returns_all_dossiers(self, mock_session_factory):
        """Sans filtre → renvoie les dossiers de la première page"""
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(
            json_data={
                "data": {
                    "demarche": {
                        "dossiers": {
                            "pageInfo": {"hasNextPage": False, "endCursor": "cur1"},
                            "nodes": [
                                {"number": 1, "state": "accepte", "dateDepot": "2026-01-01T00:00:00Z"}
                            ],
                        }
                    }
                }
            }
        )
        mock_session_factory.return_value = mock_session

        result = get_demarche_dossiers(7)

        assert len(result) == 1
        assert result[0]["number"] == 1
        mock_session.post.assert_called_once()

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_pagination_fetches_all_pages(self, mock_session_factory):
        """hasNextPage → boucle jusqu'à épuisement de la pagination"""
        page1 = {
            "data": {
                "demarche": {
                    "dossiers": {
                        "pageInfo": {"hasNextPage": True, "endCursor": "cur1"},
                        "nodes": [{"number": 1, "state": "accepte", "dateDepot": "2026-01-01T00:00:00Z"}],
                    }
                }
            }
        }
        page2 = {
            "data": {
                "demarche": {
                    "dossiers": {
                        "pageInfo": {"hasNextPage": False, "endCursor": "cur2"},
                        "nodes": [{"number": 2, "state": "accepte", "dateDepot": "2026-01-02T00:00:00Z"}],
                    }
                }
            }
        }
        mock_session = MagicMock()
        # Le dict variables est muté par référence dans la fonction : on capture
        # une copie de afterCursor à chaque appel via side_effect.
        captured_cursors = []
        pages = [_mock_response(json_data=page1), _mock_response(json_data=page2)]

        def fake_post(*args, **kwargs):
            captured_cursors.append(
                kwargs["json"]["variables"]["afterCursor"]
            )
            return pages[len(captured_cursors) - 1]

        mock_session.post.side_effect = fake_post
        mock_session_factory.return_value = mock_session

        result = get_demarche_dossiers(7)

        assert [d["number"] for d in result] == [1, 2]
        assert mock_session.post.call_count == 2
        assert captured_cursors == [None, "cur1"]

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_client_filters_applied(self, mock_session_factory):
        """Filtres client (date_fin, statuts, groupes) appliqués sur le résultat"""
        dossiers = [
            {
                "number": 1,
                "state": "accepte",
                "dateDepot": "2026-01-01T00:00:00Z",
                "groupeInstructeur": {"number": 100, "label": "Groupe A"},
            },
            {
                "number": 2,
                "state": "en_instruction",
                "dateDepot": "2026-06-01T00:00:00Z",
                "groupeInstructeur": {"number": 200, "label": "Groupe B"},
            },
            {
                "number": 3,
                "state": "accepte",
                "dateDepot": "2026-02-01T00:00:00Z",
                "groupeInstructeur": {"number": 100, "label": "Groupe A"},
            },
        ]
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(
            json_data={
                "data": {
                    "demarche": {
                        "dossiers": {
                            "pageInfo": {"hasNextPage": False, "endCursor": "cur1"},
                            "nodes": dossiers,
                        }
                    }
                }
            }
        )
        mock_session_factory.return_value = mock_session

        result = get_demarche_dossiers(
            7,
            date_fin="2026-03-01",
            statuts=["accepte"],
            groupes_instructeurs=["100"],
        )

        assert [d["number"] for d in result] == [1, 3]

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_graphql_errors_raise(self, mock_session_factory):
        """Erreurs GraphQL → Exception"""
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(
            json_data={"errors": [{"message": "Query invalide"}]}
        )
        mock_session_factory.return_value = mock_session

        with pytest.raises(Exception, match="Query invalide"):
            get_demarche_dossiers(7)


class TestGetDemarcheDossiersLabelsOnly:
    """Tests pour get_demarche_dossiers_labels_only"""

    @patch("dn.client.API_TOKEN", "")
    def test_missing_token_raises_value_error(self):
        """Token API non configuré → ValueError"""
        with pytest.raises(ValueError):
            get_demarche_dossiers_labels_only(7)

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_pagination_concatenates_pages(self, mock_session_factory):
        """Multi-pages → liste des dossiers concaténée"""
        page1 = {
            "data": {
                "demarche": {
                    "dossiers": {
                        "pageInfo": {"hasNextPage": True, "endCursor": "cur1"},
                        "nodes": [{"number": 1, "labels": [{"id": "l1", "name": "À suivre", "color": "green"}]}],
                    }
                }
            }
        }
        page2 = {
            "data": {
                "demarche": {
                    "dossiers": {
                        "pageInfo": {"hasNextPage": False, "endCursor": "cur2"},
                        "nodes": [{"number": 2, "labels": []}],
                    }
                }
            }
        }
        mock_session = MagicMock()
        mock_session.post.side_effect = [
            _mock_response(json_data=page1),
            _mock_response(json_data=page2),
        ]
        mock_session_factory.return_value = mock_session

        result = get_demarche_dossiers_labels_only(7)

        assert [d["number"] for d in result] == [1, 2]
        assert result[0]["labels"][0]["name"] == "À suivre"
        assert mock_session.post.call_count == 2


class TestGetDeletedDossiers:
    """Tests pour get_deleted_dossiers"""

    @patch("dn.client.API_TOKEN", "")
    def test_missing_token_raises_value_error(self):
        """Token API non configuré → ValueError"""
        with pytest.raises(ValueError):
            get_deleted_dossiers(7)

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_merges_deleted_and_pending(self, mock_session_factory):
        """Fusionne deletedDossiers et pendingDeletedDossiers"""
        deleted_resp = {
            "data": {
                "demarche": {
                    "deletedDossiers": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [{"number": 1, "state": "supprime"}],
                    }
                }
            }
        }
        pending_resp = {
            "data": {
                "demarche": {
                    "pendingDeletedDossiers": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [{"number": 2, "state": "en_construction"}],
                    }
                }
            }
        }
        mock_session = MagicMock()
        mock_session.post.side_effect = [
            _mock_response(json_data=deleted_resp),
            _mock_response(json_data=pending_resp),
        ]
        mock_session_factory.return_value = mock_session

        result = get_deleted_dossiers(7)

        assert [d["number"] for d in result] == [1, 2]
        assert mock_session.post.call_count == 2

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_deleted_pagination(self, mock_session_factory):
        """Pagination sur deletedDossiers puis pendingDeletedDossiers"""
        deleted_p1 = {
            "data": {
                "demarche": {
                    "deletedDossiers": {
                        "pageInfo": {"hasNextPage": True, "endCursor": "cur1"},
                        "nodes": [{"number": 1}],
                    }
                }
            }
        }
        deleted_p2 = {
            "data": {
                "demarche": {
                    "deletedDossiers": {
                        "pageInfo": {"hasNextPage": False, "endCursor": "cur2"},
                        "nodes": [{"number": 2}],
                    }
                }
            }
        }
        pending_resp = {
            "data": {
                "demarche": {
                    "pendingDeletedDossiers": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [{"number": 3}],
                    }
                }
            }
        }
        mock_session = MagicMock()
        mock_session.post.side_effect = [
            _mock_response(json_data=deleted_p1),
            _mock_response(json_data=deleted_p2),
            _mock_response(json_data=pending_resp),
        ]
        mock_session_factory.return_value = mock_session

        result = get_deleted_dossiers(7)

        assert [d["number"] for d in result] == [1, 2, 3]
        assert mock_session.post.call_count == 3