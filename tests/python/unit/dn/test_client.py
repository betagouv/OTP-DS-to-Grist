import pytest
from unittest.mock import MagicMock, patch

from utils.timing import clear_timings, get_timings
from dn.client import (
    DEMARCHES_FALLBACK_429_DELAY,
    DEMARCHES_MAX_429_RETRIES,
    DEMARCHES_MAX_RANDOM_DELAY_SECONDS,
    get_deleted_dossiers,
    get_demarche_dossiers_labels_only,
    get_groups,
    get_session_with_retries,
    iter_demarche_dossier_pages,
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

    @patch("dn.client.build_rate_limited_session")
    def test_reuses_same_session(self, mock_builder):
        """La session est un singleton : deux appels → même objet"""
        mock_builder.return_value = MagicMock()
        with patch("dn.client._session", None):
            session1 = get_session_with_retries()
            session2 = get_session_with_retries()

        assert session1 is session2
        assert mock_builder.call_count == 1

    @patch("dn.client.build_rate_limited_session")
    def test_calls_builder_with_dn_rate_limits(self, mock_builder):
        """La session est construite avec les limites 429 de DN"""
        with patch("dn.client._session", None):
            get_session_with_retries()

        mock_builder.assert_called_once_with(
            max_retries=DEMARCHES_MAX_429_RETRIES,
            fallback_delay=DEMARCHES_FALLBACK_429_DELAY,
            max_random_delay=DEMARCHES_MAX_RANDOM_DELAY_SECONDS,
        )


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
    @patch("dn.client.log")
    def test_permission_errors_are_ignored(self, mock_log, mock_session):
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
        # Le dossier masqué est nommé dans les logs, sinon il disparaît sans trace
        messages = " ".join(str(call.args[0]) for call in mock_log.call_args_list)
        assert "Dossier 2 hidden due to permissions" in messages

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

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_each_page_is_timed(self, mock_session):
        """Chaque requête de page alimente le résumé [API]"""
        session = MagicMock()
        session.post.side_effect = [
            _page([_dossier(1)], has_next_page=True, end_cursor="c1"),
            _page([_dossier(2)], has_next_page=False),
        ]
        mock_session.return_value = session

        clear_timings()
        try:
            list(iter_demarche_dossier_pages(123))
            pages = [
                t for t in get_timings() if t["function"] == "get_dossier_per_page"
            ]
        finally:
            clear_timings()

        assert [t["service"] for t in pages] == ["ds", "ds"]

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_without_server_filters_queries_demarche(self, mock_session):
        """Sans filtre serveur : racine démarche, statut et date de dépôt à null"""
        session = MagicMock()
        session.post.return_value = _page([_dossier(1)])
        mock_session.return_value = session

        list(iter_demarche_dossier_pages(123))

        query = session.post.call_args.kwargs["json"]["query"]
        variables = session.post.call_args.kwargs["json"]["variables"]
        assert "demarche(number: $demarcheNumber)" in query
        assert "groupeInstructeur(number:" not in query
        assert variables["demarcheNumber"] == 123
        assert "groupeNumber" not in variables
        assert variables["state"] is None
        assert variables["createdSince"] is None

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_groupe_number_queries_groupe_instructeur(self, mock_session):
        """Avec un groupe : racine groupeInstructeur, pagination lue sous cette racine"""
        session = MagicMock()
        session.post.side_effect = [
            _groupe_page([_dossier(1)], has_next_page=True, end_cursor="c1"),
            _groupe_page([_dossier(2)], has_next_page=False),
        ]
        mock_session.return_value = session

        pages = list(iter_demarche_dossier_pages(123, groupe_number=120382))

        assert [[dossier["number"] for dossier in page] for page in pages] == [[1], [2]]
        first_call = session.post.call_args_list[0].kwargs["json"]
        assert "groupeInstructeur(number: $groupeNumber)" in first_call["query"]
        assert "demarche(number:" not in first_call["query"]
        assert "champs" in first_call["query"] and "annotations" in first_call["query"]
        assert first_call["variables"]["groupeNumber"] == 120382
        assert "demarcheNumber" not in first_call["variables"]
        curseurs = [
            appel.kwargs["json"]["variables"]["afterCursor"]
            for appel in session.post.call_args_list
        ]
        assert curseurs == [None, "c1"]

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_state_and_created_since_are_transmitted(self, mock_session):
        """Le statut et la borne de dépôt sont transmis tels quels à l'API"""
        session = MagicMock()
        session.post.return_value = _page([_dossier(1)])
        mock_session.return_value = session

        list(
            iter_demarche_dossier_pages(
                123, state="en_instruction", created_since="2025-12-31T00:00:00Z"
            )
        )

        variables = session.post.call_args.kwargs["json"]["variables"]
        assert variables["state"] == "en_instruction"
        assert variables["createdSince"] == "2025-12-31T00:00:00Z"

    @patch("dn.client.get_session_with_retries")
    @patch("dn.client.API_TOKEN", "test-token")
    def test_inaccessible_groupe_yields_nothing(self, mock_session):
        """Groupe inaccessible (null) → aucune page, pas d'erreur"""
        session = MagicMock()
        session.post.return_value = _mock_response(
            json_data={"data": {"groupeInstructeur": None}}
        )
        mock_session.return_value = session

        assert list(iter_demarche_dossier_pages(123, groupe_number=1)) == []


def _groupe_page(nodes, has_next_page=False, end_cursor=None):
    payload = {
        "data": {
            "groupeInstructeur": {
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
    return _mock_response(json_data=payload)
