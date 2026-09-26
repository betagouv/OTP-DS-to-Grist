import pytest
from unittest.mock import MagicMock, patch

import requests

from dn.client import (
    iter_demarche_dossier_pages,
    FALLBACK_429_DELAY,
    MAX_429_RETRIES,
    MAX_RANDOM_DELAY_SECONDS,
    RateLimitedSession,
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


class TestRetryDelay:
    """Tests pour RateLimitedSession._retry_delay"""

    def test_retry_after_header_used(self):
        """Retry-After présent → le délai est son nombre de secondes"""
        session = RateLimitedSession()

        with patch("random.uniform", return_value=0):
            assert session._retry_delay(_mock_response(429, headers={"Retry-After": "15"})) == 15.0

    def test_retry_after_takes_precedence_over_reset(self):
        """Retry-After présent → prioritaire sur RateLimit-Reset"""
        session = RateLimitedSession()
        response = _mock_response(429, headers={"Retry-After": "10", "RateLimit-Reset": "9999999999"})

        with patch("random.uniform", return_value=0), patch("time.time", return_value=0):
            assert session._retry_delay(response) == 10.0

    def test_rate_limit_reset_used_when_no_retry_after(self):
        """Sans Retry-After → RateLimit-Reset moins l'heure courante"""
        session = RateLimitedSession()

        with patch("random.uniform", return_value=0), patch("time.time", return_value=40):
            assert session._retry_delay(_mock_response(429, headers={"RateLimit-Reset": "100"})) == 60.0

    def test_reset_in_past_is_clamped_to_zero(self):
        """RateLimit-Reset déjà passé → délai écrasé à 0"""
        session = RateLimitedSession()

        with patch("random.uniform", return_value=0), patch("time.time", return_value=100):
            assert session._retry_delay(_mock_response(429, headers={"RateLimit-Reset": "50"})) == 0.0

    def test_fallback_delay_when_no_headers(self):
        """Ni Retry-After ni RateLimit-Reset → délai de repli"""
        session = RateLimitedSession()

        with patch("random.uniform", return_value=0):
            assert session._retry_delay(_mock_response(429)) == FALLBACK_429_DELAY

    def test_jitter_is_uniform_and_bounded(self):
        """Un délai aléatoire borné est ajouté au délai du serveur"""
        session = RateLimitedSession()

        with patch("random.uniform") as mock_uniform:
            mock_uniform.return_value = 3.5
            assert session._retry_delay(_mock_response(429, headers={"Retry-After": "10"})) == 13.5
            mock_uniform.assert_called_once_with(0, MAX_RANDOM_DELAY_SECONDS)


class TestRateLimitedSession:
    """Tests pour le comportement 429 de RateLimitedSession"""

    @patch.object(requests.Session, "request")
    @patch("dn.client.log")
    @patch("time.sleep")
    def test_non_429_returned_immediately(self, mock_sleep, mock_log, mock_request):
        """Réponse non-429 → renvoyée telle quelle, sans attente ni log"""
        mock_request.return_value = _mock_response(200)

        response = RateLimitedSession().request("POST", "http://dn")

        assert response.status_code == 200
        mock_request.assert_called_once_with("POST", "http://dn")
        mock_sleep.assert_not_called()
        mock_log.assert_not_called()

    @patch.object(requests.Session, "request")
    @patch("dn.client.log")
    @patch("time.sleep")
    def test_success_on_second_attempt(self, mock_sleep, mock_log, mock_request):
        """429 puis 200 → le délai est attendu puis la requête est relancée"""
        mock_request.side_effect = [
            _mock_response(429, headers={"Retry-After": "10"}),
            _mock_response(200),
        ]

        with patch("random.uniform", return_value=0):
            response = RateLimitedSession().request("POST", "http://dn")

        assert response.status_code == 200
        assert mock_request.call_count == 2
        mock_sleep.assert_called_once_with(10.0)

    @patch.object(requests.Session, "request")
    @patch("dn.client.log")
    @patch("time.sleep")
    def test_log_mentions_429_and_delay(self, mock_sleep, mock_log, mock_request):
        """Le log mentionne le 429 et le délai d'attente"""
        mock_request.side_effect = [
            _mock_response(429, headers={"Retry-After": "10"}),
            _mock_response(200),
        ]

        with patch("random.uniform", return_value=0):
            RateLimitedSession().request("POST", "http://dn")

        assert mock_log.call_count == 1
        message = mock_log.call_args[0][0]
        assert "429" in message
        assert "10" in message

    @patch.object(requests.Session, "request")
    @patch("dn.client.log")
    @patch("time.sleep")
    def test_exhaustion_returns_429(self, mock_sleep, mock_log, mock_request):
        """Essais épuisés → la dernière réponse 429 remonte"""
        mock_request.side_effect = [
            _mock_response(429, headers={"Retry-After": "10"}),
            _mock_response(429, headers={"Retry-After": "10"}),
            _mock_response(429, headers={"Retry-After": "10"}),
        ]

        with patch("random.uniform", return_value=0):
            response = RateLimitedSession().request("POST", "http://dn")

        assert response.status_code == 429
        assert mock_request.call_count == MAX_429_RETRIES
        assert mock_sleep.call_count == MAX_429_RETRIES - 1
        assert mock_log.call_count == MAX_429_RETRIES - 1

    @patch.object(requests.Session, "request")
    @patch("dn.client.log")
    @patch("time.sleep")
    def test_5xx_returned_without_retry(self, mock_sleep, mock_log, mock_request):
        """5xx → renvoyé sans relance (géré par l'adapter urllib3)"""
        mock_request.return_value = _mock_response(500)

        response = RateLimitedSession().request("POST", "http://dn")

        assert response.status_code == 500
        mock_request.assert_called_once()
        mock_sleep.assert_not_called()
        mock_log.assert_not_called()

    @patch.object(requests.Session, "request")
    @patch("dn.client.log")
    @patch("time.sleep")
    def test_get_verb_uses_same_protection(self, mock_sleep, mock_log, mock_request):
        """Le verbe GET passe par le même mécanisme anti-429"""
        mock_request.side_effect = [
            _mock_response(429, headers={"Retry-After": "5"}),
            _mock_response(200),
        ]

        with patch("random.uniform", return_value=0):
            response = RateLimitedSession().get("http://dn")

        assert response.status_code == 200
        assert mock_request.call_count == 2
        mock_sleep.assert_called_once_with(5.0)

def _dossier(number, **champs):
    """Dossier détaillé minimal, tel que renvoyé par la connexion paginée."""
    dossier = {
        "number": number,
        "state": "instruite",
        "dateDepot": "2024-01-01T00:00:00+01:00",
        "dateDerniereModification": "2024-02-01T00:00:00+01:00",
        "motivation": "because",
        "usager": {"email": "usager@example.com"},
        "champs": [],
        "annotations": [],
    }
    dossier.update(champs)
    return dossier


def _page(nodes, has_next_page=False, end_cursor=None, errors=None):
    payload = {
        "data": {
            "demarche": {
                "dossiers": {
                    "pageInfo": {
                        "hasNextPage": has_next_page,
                        "endCursor": end_cursor,
                    },
                    "nodes": nodes,
                }
            }
        }
    }
    if errors is not None:
        payload["errors"] = errors
    return _mock_response(json_data=payload)


class TestIterDemarcheDossierPages:
    """Tests pour iter_demarche_dossier_pages (pagination des dossiers détaillés)"""

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_missing_token_raises(self, _mock_session):
        """Token manquant → ValueError, aucune requête"""
        with patch("dn.client.API_TOKEN", ""):
            with pytest.raises(ValueError):
                list(iter_demarche_dossier_pages(123))
        _mock_session.assert_not_called()

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_yields_dossiers_page_by_page(self, mock_session):
        """Chaque page est rendue dès sa réception, avec le curseur de la page suivante"""
        session = MagicMock()
        session.post.side_effect = [
            _page([_dossier(1), _dossier(2)], has_next_page=True, end_cursor="c1"),
            _page([_dossier(3)], has_next_page=False, end_cursor="c2"),
        ]
        mock_session.return_value = session

        pages = list(iter_demarche_dossier_pages(123))

        assert [[dossier["number"] for dossier in page] for page in pages] == [
            [1, 2],
            [3],
        ]
        curseurs = [
            appel.kwargs["json"]["variables"]["afterCursor"]
            for appel in session.post.call_args_list
        ]
        assert curseurs == [None, "c1"]

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_query_requests_detailed_dossiers(self, mock_session):
        """La page est détaillée (champs, annotations, avis), sans filtre serveur"""
        session = MagicMock()
        session.post.return_value = _page([_dossier(1)])
        mock_session.return_value = session

        list(iter_demarche_dossier_pages(123))

        variables = session.post.call_args.kwargs["json"]["variables"]
        query = session.post.call_args.kwargs["json"]["query"]
        assert variables["includeChamps"] is True
        assert variables["includeAnotations"] is True
        assert variables["includeAvis"] is True
        assert "champs" in query and "annotations" in query
        assert "apiFilters" not in query

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_page_size_is_capped(self, mock_session):
        """La taille de page est transmise, bornée au maximum DN"""
        session = MagicMock()
        session.post.return_value = _page([_dossier(1)])
        mock_session.return_value = session

        list(iter_demarche_dossier_pages(123, page_size=500))

        assert session.post.call_args.kwargs["json"]["variables"]["first"] == 100

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_updated_since_is_transmitted(self, mock_session):
        """Le repère de reprise est transmis à l'API"""
        session = MagicMock()
        session.post.return_value = _page([_dossier(1)])
        mock_session.return_value = session

        list(iter_demarche_dossier_pages(123, updated_since="2024-06-01T00:00:00Z"))

        variables = session.post.call_args.kwargs["json"]["variables"]
        assert variables["updatedSince"] == "2024-06-01T00:00:00Z"

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_injected_session_is_used(self, mock_session):
        """La session injectée est utilisée telle quelle (pas de session globale)"""
        session = MagicMock()
        session.post.return_value = _page([_dossier(1)])

        list(iter_demarche_dossier_pages(123, session=session))

        session.post.assert_called_once()
        mock_session.assert_not_called()

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_display_only_champs_are_filtered(self, mock_session):
        """En-têtes de section et explications retirés des champs et annotations"""
        session = MagicMock()
        session.post.return_value = _page(
            [
                _dossier(
                    1,
                    champs=[
                        {"__typename": "TextChamp", "id": "c1"},
                        {"__typename": "HeaderSectionChamp", "id": "c2"},
                        {"__typename": "ExplicationChamp", "id": "c3"},
                    ],
                    annotations=[
                        {"__typename": "TextChamp", "id": "a1"},
                        {"__typename": "ExplicationChamp", "id": "a2"},
                    ],
                )
            ]
        )
        mock_session.return_value = session

        page = next(iter_demarche_dossier_pages(123))

        assert [champ["id"] for champ in page[0]["champs"]] == ["c1"]
        assert [annotation["id"] for annotation in page[0]["annotations"]] == ["a1"]

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_permission_errors_are_ignored(self, mock_session):
        """Les dossiers masqués par les permissions n'interrompent pas la pagination"""
        session = MagicMock()
        session.post.side_effect = [
            _page(
                [_dossier(1)],
                has_next_page=True,
                end_cursor="c1",
                errors=[{"message": "Dossier 2 hidden due to permissions"}],
            ),
            _page([_dossier(3)], has_next_page=False, end_cursor="c2"),
        ]
        mock_session.return_value = session

        pages = list(iter_demarche_dossier_pages(123))

        assert [[dossier["number"] for dossier in page] for page in pages] == [[1], [3]]

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_non_permission_errors_raise(self, mock_session):
        """Une autre erreur GraphQL interrompt la pagination"""
        session = MagicMock()
        session.post.return_value = _mock_response(
            json_data={
                "data": {"demarche": None},
                "errors": [{"message": "Erreur interne du serveur"}],
            }
        )
        mock_session.return_value = session

        with pytest.raises(Exception, match="Erreur interne"):
            list(iter_demarche_dossier_pages(123))

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_inaccessible_demarche_yields_nothing(self, mock_session):
        """Démarche inaccessible (null) → aucune page, pas d'erreur"""
        session = MagicMock()
        session.post.return_value = _mock_response(json_data={"data": {"demarche": None}})
        mock_session.return_value = session

        assert list(iter_demarche_dossier_pages(123)) == []

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_single_page_stops_pagination(self, mock_session):
        """hasNextPage à false → une seule requête"""
        session = MagicMock()
        session.post.return_value = _page([_dossier(1)], has_next_page=False)
        mock_session.return_value = session

        assert len(list(iter_demarche_dossier_pages(123))) == 1
        session.post.assert_called_once()

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_empty_page_does_not_loop_forever(self, mock_session):
        """Page vide et curseur immobile → arrêt sans boucle infinie"""
        session = MagicMock()
        session.post.return_value = _page([], has_next_page=True, end_cursor=None)
        mock_session.return_value = session

        assert list(iter_demarche_dossier_pages(123)) == []
        assert session.post.call_count == 1
