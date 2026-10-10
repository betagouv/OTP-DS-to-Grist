from unittest.mock import MagicMock, patch

from schema_utils import (
    get_problematic_descriptor_ids_from_schema,
    auto_clean_schema_descriptors,
    create_columns_from_schema,
    get_demarche_schema,
    update_grist_tables_from_schema,
)


class TestSchemaUtils:
    """Tests unitaires pour les utilitaires de schéma"""

    def test_get_problematic_descriptor_ids_from_schema(self):
        """Test l'extraction des IDs problématiques"""
        schema = {
            "activeRevision": {
                "champDescriptors": [
                    {
                        "id": "1",
                        "__typename": "TextChampDescriptor",
                        "type": "text"
                    },
                    {
                        "id": "2",
                        "__typename": "HeaderSectionChampDescriptor",
                        "type": "header_section"
                    },
                    {
                        "id": "3",
                        "__typename": "ExplicationChampDescriptor",
                        "type": "explication"
                    },
                    {
                        "__typename": "RepetitionChampDescriptor",
                        "champDescriptors": [
                            {
                                "id": "4",
                                "__typename": "TextChampDescriptor",
                                "type": "text"
                            },
                            {
                                "id": "5",
                                "__typename": "HeaderSectionChampDescriptor",
                                "type": "header_section"
                            }
                        ]
                    }
                ],
                "annotationDescriptors": [
                    {
                        "id": "6",
                        "__typename": "TextChampDescriptor",
                        "type": "text"
                    },
                    {
                        "id": "7",
                        "__typename": "ExplicationChampDescriptor",
                        "type": "explication"
                    }
                ]
            }
        }

        problematic_ids = get_problematic_descriptor_ids_from_schema(schema)

        expected_ids = {"2", "3", "5", "7"}
        assert problematic_ids == expected_ids

    def test_get_problematic_descriptor_ids_empty_schema(self):
        """Test avec un schéma vide"""
        schema = {
            "activeRevision": {
                "champDescriptors": [],
                "annotationDescriptors": []
            }
        }
        problematic_ids = get_problematic_descriptor_ids_from_schema(schema)
        assert problematic_ids == set()

    def test_get_problematic_descriptor_ids_no_active_revision(self):
        """Test sans révision active"""
        schema = {}
        problematic_ids = get_problematic_descriptor_ids_from_schema(schema)
        assert problematic_ids == set()

    def test_auto_clean_schema_descriptors(self):
        """Test le nettoyage automatique des descripteurs"""
        schema = {
            "activeRevision": {
                "champDescriptors": [
                    {
                        "id": "1",
                        "__typename": "TextChampDescriptor",
                        "type": "text",
                        "label": "Text"
                    },
                    {
                        "id": "2",
                        "__typename": "HeaderSectionChampDescriptor",
                        "type": "header_section",
                        "label": "Header"
                    },
                    {
                        "id": "3",
                        "__typename": "ExplicationChampDescriptor",
                        "type": "explication",
                        "label": "Explication"
                    },
                    {
                        "__typename": "RepetitionChampDescriptor",
                        "champDescriptors": [
                            {
                                "id": "4",
                                "__typename": "TextChampDescriptor",
                                "type": "text",
                                "label": "Inner Text"
                            },
                            {
                                "id": "5",
                                "__typename": "HeaderSectionChampDescriptor",
                                "type": "header_section",
                                "label": "Inner Header"
                            }
                        ]
                    }
                ],
                "annotationDescriptors": [
                    {
                        "id": "6",
                        "__typename": "TextChampDescriptor",
                        "type": "text",
                        "label": "Annotation"
                    },
                    {
                        "id": "7",
                        "__typename": "ExplicationChampDescriptor",
                        "type": "explication",
                        "label": "Annotation Expl"
                    }
                ]
            }
        }

        cleaned = auto_clean_schema_descriptors(schema)

        # Vérifier que les champs problématiques sont filtrés
        champ_descriptors = cleaned["activeRevision"]["champDescriptors"]
        assert len(champ_descriptors) == 2  # Text + Repetition nettoyé

        # Le bloc répétable devrait avoir un sous-champ nettoyé
        repetition = next(
            d for d in champ_descriptors
            if d.get("__typename") == "RepetitionChampDescriptor"
        )
        assert len(repetition["champDescriptors"]) == 1  # Seulement le Text

        # Annotations nettoyées
        annotation_descriptors = cleaned[
            "activeRevision"
        ]["annotationDescriptors"]
        assert len(annotation_descriptors) == 1  # Seulement le Text

    def test_auto_clean_schema_descriptors_empty(self):
        """Test avec un schéma vide"""
        schema = {
            "activeRevision": {
                "champDescriptors": [],
                "annotationDescriptors": []
            }
        }
        cleaned = auto_clean_schema_descriptors(schema)
        assert cleaned == schema


class TestUpdateGristTablesFromSchema:
    """Tests unitaires pour la fonction imbriquée add_missing_columns
    via update_grist_tables_from_schema"""

    def setup_method(self):
        self.client = MagicMock()
        self.client.base_url = "https://grist.example.com"
        self.client.doc_id = "doc1"
        self.client.headers = {}
        self.client.list_tables = MagicMock(
            return_value={"tables": [{"id": "Demarche_123_dossiers"}]}
        )
        self.client.create_table = MagicMock(
            return_value={"tables": [{"id": "creee", "columns": []}]}
        )

    def _column_types(self):
        return {
            "dossier": [{"id": "nouveau_col", "type": "Text"}],
            "champs": [{"id": "existant", "type": "Text"}],
            "annotations": [{"id": "dossier_number", "type": "Int"}],
        }

    def test_adds_only_missing_columns(self):
        """seules les colonnes manquantes de la table dossiers sont POSTées"""
        self.client.get_columns.return_value = {"existant": "Text"}
        post_response = MagicMock()
        post_response.status_code = 200
        self.client.add_columns.return_value = post_response
        with (
            patch("schema_utils.API_TOKEN", "fake-token"),
            patch("schema_utils.requests.post") as mock_post,
        ):
            result = update_grist_tables_from_schema(
                self.client, 123, self._column_types()
            )
        assert result["dossiers"] == "Demarche_123_dossiers"
        self.client.add_columns.assert_called_once()
        assert self.client.add_columns.call_args.args[0] == "Demarche_123_dossiers"
        assert self.client.add_columns.call_args.args[1] == [
            {"id": "nouveau_col", "type": "Text"}
        ]
        assert mock_post.call_count == 1
        assert "columns" not in mock_post.call_args.kwargs["json"]

    def test_get_error_no_post(self):
        """GET en échec -> aucun POST de colonnes"""
        self.client.get_columns.return_value = {}
        with (
            patch("schema_utils.API_TOKEN", "fake-token"),
            patch("schema_utils.requests.post") as mock_post,
        ):
            result = update_grist_tables_from_schema(
                self.client, 123, self._column_types()
            )
        assert result["dossiers"] == "Demarche_123_dossiers"
        self.client.add_columns.assert_not_called()
        column_posts = [
            c
            for c in mock_post.call_args_list
            if "columns" in c.kwargs.get("json", {})
        ]
        assert column_posts == []


RIB_SUFFIXES = ["titulaire", "iban", "bic", "nom_de_la_banque"]


def _make_pj_schema(label, descriptor_id="desc_pj", pj_natures=None):
    schema = {
        "title": "Test démarche",
        "activeRevision": {
            "id": "rev_1",
            "champDescriptors": [
                {
                    "__typename": "PieceJustificativeChampDescriptor",
                    "id": descriptor_id,
                    "type": "piece_justificative",
                    "label": label,
                    "description": "",
                    "required": False,
                }
            ],
            "annotationDescriptors": [],
        },
    }
    if pj_natures is not None:
        schema["pj_natures"] = pj_natures
    return schema


def _champ_column_ids(schema):
    column_types, _ = create_columns_from_schema(schema)
    return {col["id"] for col in column_types["champs"]}


class TestCreateColumnsFromSchemaRib:
    """Tests sur la création des sous-colonnes OCR RIB dans create_columns_from_schema"""

    def test_nature_rib_sans_mot_cle_cree_les_sous_colonnes(self):
        """Régression #556 : un RIB libellé sans « rib »/« iban » n'avait aucune colonne"""
        schema = _make_pj_schema("Coordonnées bancaires", pj_natures={"desc_pj": "RIB"})
        ids = _champ_column_ids(schema)
        assert {f"coordonnees_bancaires_{s}" for s in RIB_SUFFIXES} <= ids
        assert "coordonnees_bancaires" in ids

    def test_nature_non_rib_ne_cree_pas_de_sous_colonnes(self):
        """La nature fait foi sur le libellé"""
        schema = _make_pj_schema("RIB scanné", pj_natures={"desc_pj": "NON_SPECIFIE"})
        ids = _champ_column_ids(schema)
        assert ids == {"dossier_number", "champ_id", "rib_scanne"}

    def test_sans_nature_repli_sur_mot_cle(self):
        """Démarche sans dossier : repli sur le libellé"""
        ids = _champ_column_ids(_make_pj_schema("RIB du demandeur"))
        assert {f"rib_du_demandeur_{s}" for s in RIB_SUFFIXES} <= ids

    def test_sans_nature_ni_mot_cle_pas_de_sous_colonnes(self):
        ids = _champ_column_ids(_make_pj_schema("Coordonnées bancaires"))
        assert ids == {"dossier_number", "champ_id", "coordonnees_bancaires"}

    def test_nature_d_une_autre_pj_ignoree(self):
        """Une nature connue pour un autre descripteur ne s'applique pas"""
        schema = _make_pj_schema(
            "RIB du demandeur", pj_natures={"autre_desc": "NON_SPECIFIE"}
        )
        ids = _champ_column_ids(schema)
        assert {f"rib_du_demandeur_{s}" for s in RIB_SUFFIXES} <= ids


class TestGetDemarcheSchemaPjNatures:
    """Tests sur la récupération des natures des PJ par get_demarche_schema"""

    def _mock_schema_response(self, demarche):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"data": {"demarche": demarche}}
        return response

    @patch("schema_utils.API_TOKEN", "token")
    @patch("schema_utils.get_pj_natures", return_value={"desc_pj": "RIB"})
    @patch("schema_utils.requests.post")
    def test_natures_ajoutees_si_pj(self, mock_post, mock_natures):
        demarche = _make_pj_schema("Coordonnées bancaires")
        mock_post.return_value = self._mock_schema_response(demarche)

        result = get_demarche_schema(123)

        mock_natures.assert_called_once_with(123)
        assert result["pj_natures"] == {"desc_pj": "RIB"}

    @patch("schema_utils.API_TOKEN", "token")
    @patch("schema_utils.get_pj_natures")
    @patch("schema_utils.requests.post")
    def test_pas_d_appel_sans_pj(self, mock_post, mock_natures):
        demarche = {
            "title": "Test démarche",
            "activeRevision": {
                "id": "rev_1",
                "champDescriptors": [
                    {"__typename": "TextChampDescriptor", "id": "d1", "label": "Nom"}
                ],
                "annotationDescriptors": [],
            },
        }
        mock_post.return_value = self._mock_schema_response(demarche)

        result = get_demarche_schema(123)

        mock_natures.assert_not_called()
        assert "pj_natures" not in result
