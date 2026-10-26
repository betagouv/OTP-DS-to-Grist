from unittest.mock import MagicMock, patch

import pytest
import requests

from dn.extract import PJ_OCR_VALUE_KEYS
from schema_utils import (
    PJ_OCR_GRIST_TYPES,
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

# Sous-colonnes renvoyées par DN selon la nature (libellés et types repris des
# définitions DN : PieceJustificativeTypeDeChamp#columns et locales).
_DN_ADDRESS = [
    ("Code postal (5 chiffres)", "TextColumn"),
    ("Commune", "TextColumn"),
    ("Département", "EnumColumn"),
    ("Région", "EnumColumn"),
]
_DN_OCR_SUBCOLUMNS = {
    "RIB": [
        ("Titulaire", "TextColumn"),
        ("IBAN", "TextColumn"),
        ("BIC", "TextColumn"),
        ("Nom de la Banque", "TextColumn"),
    ],
    "JUSTIFICATIF_DOMICILE": [
        ("Bénéficiaire", "TextColumn"),
        ("Adresse", "TextColumn"),
        ("Date d’émission", "DateColumn"),
        *_DN_ADDRESS,
    ],
    "AVIS_IMPOT": [
        ("Déclarant 1", "TextColumn"),
        ("Déclarant 2", "TextColumn"),
        ("Référence de l’avis", "TextColumn"),
        ("Année des revenus", "IntegerColumn"),
        ("Nombre de parts", "DecimalColumn"),
        ("Revenu fiscal de référence", "IntegerColumn"),
        ("Date de mise en recouvrement", "DateColumn"),
        *_DN_ADDRESS,
    ],
}


def _dn_ocr_columns(label, nature):
    """Sous-colonnes OCR telles que renvoyées par get_pj_ocr_columns"""
    return [
        (f"{label} – {sub_label}", dn_type)
        for sub_label, dn_type in _DN_OCR_SUBCOLUMNS.get(nature, [])
    ]


def _make_pj_schema(label, descriptor_id="desc_pj", pj_ocr_columns=None):
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
    if pj_ocr_columns is not None:
        schema["pj_ocr_columns"] = pj_ocr_columns
    return schema


def _champ_column_ids(schema):
    column_types, _ = create_columns_from_schema(schema)
    return {col["id"] for col in column_types["champs"]}


class TestCreateColumnsFromSchemaRib:
    """Tests sur la création des sous-colonnes OCR RIB dans create_columns_from_schema"""

    def test_nature_rib_sans_mot_cle_cree_les_sous_colonnes(self):
        """Régression #556 : un RIB libellé sans « rib »/« iban » n'avait aucune colonne"""
        schema = _make_pj_schema(
            "Coordonnées bancaires",
            pj_ocr_columns={"desc_pj": _dn_ocr_columns("Coordonnées bancaires", "RIB")},
        )
        ids = _champ_column_ids(schema)
        assert {f"coordonnees_bancaires_{s}" for s in RIB_SUFFIXES} <= ids
        assert "coordonnees_bancaires" in ids

    def test_pj_sans_ocr_ne_cree_pas_de_sous_colonnes(self):
        """Les colonnes renvoyées par DN font foi sur le libellé"""
        schema = _make_pj_schema("RIB scanné", pj_ocr_columns={"desc_pj": []})
        ids = _champ_column_ids(schema)
        assert ids == {"dossier_number", "champ_id", "rib_scanne"}

    def test_sans_dossier_repli_sur_mot_cle(self):
        """Démarche sans dossier : repli sur le libellé"""
        ids = _champ_column_ids(_make_pj_schema("RIB du demandeur"))
        assert {f"rib_du_demandeur_{s}" for s in RIB_SUFFIXES} <= ids

    def test_sans_dossier_ni_mot_cle_pas_de_sous_colonnes(self):
        ids = _champ_column_ids(_make_pj_schema("Coordonnées bancaires"))
        assert ids == {"dossier_number", "champ_id", "coordonnees_bancaires"}

    def test_colonnes_d_une_autre_pj_ignorees(self):
        """Les colonnes connues pour un autre descripteur ne s'appliquent pas"""
        schema = _make_pj_schema("RIB du demandeur", pj_ocr_columns={"autre_desc": []})
        ids = _champ_column_ids(schema)
        assert {f"rib_du_demandeur_{s}" for s in RIB_SUFFIXES} <= ids


class TestCreateColumnsFromSchemaPjOcr:
    """Tests sur les sous-colonnes OCR des autres natures de pièces justificatives"""

    def _ocr_types(self, label, nature):
        schema = _make_pj_schema(
            label, pj_ocr_columns={"desc_pj": _dn_ocr_columns(label, nature)}
        )
        column_types, _ = create_columns_from_schema(schema)
        return {
            col["id"]: col["fields"]["type"]
            for col in column_types["champs"]
            if col["id"] not in {"dossier_number", "champ_id", "justificatif", "avis"}
        }

    def test_justificatif_domicile(self):
        assert self._ocr_types("Justificatif", "JUSTIFICATIF_DOMICILE") == {
            "justificatif_beneficiaire": "Text",
            "justificatif_adresse": "Text",
            "justificatif_date_d_emission": "Date",
            "justificatif_code_postal_5_chiffres": "Text",
            "justificatif_commune": "Text",
            "justificatif_departement": "Text",
            "justificatif_region": "Text",
        }

    def test_avis_impot(self):
        assert self._ocr_types("Avis", "AVIS_IMPOT") == {
            "avis_declarant_1": "Text",
            "avis_declarant_2": "Text",
            "avis_reference_de_l_avis": "Text",
            "avis_annee_des_revenus": "Int",
            "avis_nombre_de_parts": "Numeric",
            "avis_revenu_fiscal_de_reference": "Int",
            "avis_date_de_mise_en_recouvrement": "Date",
            "avis_code_postal_5_chiffres": "Text",
            "avis_commune": "Text",
            "avis_departement": "Text",
            "avis_region": "Text",
        }

    def test_libelle_affiche_comme_dn(self):
        schema = _make_pj_schema(
            "Avis", pj_ocr_columns={"desc_pj": _dn_ocr_columns("Avis", "AVIS_IMPOT")}
        )
        column_types, _ = create_columns_from_schema(schema)
        labels = {
            col["fields"]["label"] for col in column_types["champs"] if "fields" in col
        }
        assert "Avis – Nombre de parts" in labels

    def test_sans_dossier_pas_de_repli_hors_rib(self):
        """Le repli sur le libellé ne vaut que pour le RIB"""
        ids = _champ_column_ids(_make_pj_schema("Avis d'impôt"))
        assert ids == {"dossier_number", "champ_id", "avis_d_impot"}

    def test_libelles_suivis_depuis_dn(self):
        """Libellé ou nature inconnus du code : repris tels que DN les renvoie"""
        schema = _make_pj_schema(
            "Facture",
            pj_ocr_columns={
                "desc_pj": [
                    ("Facture – Montant TTC", "DecimalColumn"),
                    ("Facture – Échéance", "DateColumn"),
                ]
            },
        )
        column_types, _ = create_columns_from_schema(schema)
        fields = {
            col["id"]: col["fields"]
            for col in column_types["champs"]
            if "fields" in col
        }
        assert fields["facture_montant_ttc"] == {
            "type": "Numeric",
            "label": "Facture – Montant TTC",
        }
        assert fields["facture_echeance"]["type"] == "Date"

    def test_types_non_lus_par_l_extraction_ignores(self):
        """Sous-colonne d'un type que dn.extract ne lit pas -> pas de colonne"""
        schema = _make_pj_schema(
            "Avis", pj_ocr_columns={"desc_pj": [("Avis – Coché", "BooleanColumn")]}
        )
        assert _champ_column_ids(schema) == {"dossier_number", "champ_id", "avis"}

    def test_types_grist_alignes_sur_l_extraction(self):
        """Chaque type lu par dn.extract a un type Grist, et inversement"""
        assert PJ_OCR_GRIST_TYPES.keys() == PJ_OCR_VALUE_KEYS.keys()


def _make_block_pj_schema(pj_ocr_columns=None):
    schema = {
        "title": "Test démarche",
        "activeRevision": {
            "id": "rev_1",
            "champDescriptors": [
                {
                    "__typename": "RepetitionChampDescriptor",
                    "id": "desc_bloc",
                    "type": "repetition",
                    "label": "Foyer",
                    "champDescriptors": [
                        {
                            "__typename": "PieceJustificativeChampDescriptor",
                            "id": "desc_pj",
                            "type": "piece_justificative",
                            "label": "Avis",
                        }
                    ],
                }
            ],
            "annotationDescriptors": [],
        },
    }
    if pj_ocr_columns is not None:
        schema["pj_ocr_columns"] = pj_ocr_columns
    return schema


class TestCreateColumnsFromSchemaPjOcrBlocs:
    """Tests sur les sous-colonnes OCR des pièces justificatives des blocs répétables"""

    def _block_types(self, schema):
        column_types, _ = create_columns_from_schema(schema)
        block = column_types["repetable_blocks"]["foyer"]
        return {col["id"]: col["type"] for col in block["columns"]}

    def test_avis_impot_dans_un_bloc(self):
        types = self._block_types(
            _make_block_pj_schema({"desc_pj": _dn_ocr_columns("Avis", "AVIS_IMPOT")})
        )
        assert types["avis"] == "Text"
        assert types["avis_nombre_de_parts"] == "Numeric"
        assert types["avis_revenu_fiscal_de_reference"] == "Int"
        assert types["avis_date_de_mise_en_recouvrement"] == "Date"
        assert types["avis_region"] == "Text"

    def test_pj_sans_ocr_dans_un_bloc(self):
        types = self._block_types(_make_block_pj_schema({"desc_pj": []}))
        assert not [col for col in types if col.startswith("avis_")]


class TestGetDemarcheSchemaPjOcrColumns:
    """Tests sur la récupération des sous-colonnes OCR des PJ par get_demarche_schema"""


def _mock_graphql_response(payload):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = payload
    return response


def _text_demarche():
    return {
        "title": "Test démarche",
        "activeRevision": {
            "id": "rev_1",
            "champDescriptors": [
                {"__typename": "TextChampDescriptor", "id": "d1", "label": "Nom"}
            ],
            "annotationDescriptors": [],
        },
    }


# Les appels HTTP sont simulés au niveau de requests.Session.request, commun à
# requests.post et aux sessions : les tests ne dépendent pas du client utilisé.
@patch("dn.client.API_TOKEN", "token")
@patch("schema_utils.API_TOKEN", "token")
@patch.object(requests.Session, "request")
class TestGetDemarcheSchema:
    """Tests sur la récupération du schéma d'une démarche par get_demarche_schema"""

    @patch(
        "schema_utils.get_pj_ocr_columns",
        return_value={"desc_pj": [("RIB – IBAN", "TextColumn")]},
    )
    def test_colonnes_ajoutees_si_pj(self, mock_natures, mock_request):
        demarche = _make_pj_schema("Coordonnées bancaires")
        mock_request.return_value = _mock_graphql_response(
            {"data": {"demarche": demarche}}
        )

        result = get_demarche_schema(123)

        mock_natures.assert_called_once_with(123)
        assert result["pj_ocr_columns"] == {"desc_pj": [("RIB – IBAN", "TextColumn")]}

    @patch("schema_utils.get_pj_ocr_columns", return_value={"desc_pj": []})
    def test_colonnes_ajoutees_si_pj_dans_un_bloc(self, mock_natures, mock_request):
        mock_request.return_value = _mock_graphql_response(
            {"data": {"demarche": _make_block_pj_schema()}}
        )

        result = get_demarche_schema(123)

        mock_natures.assert_called_once_with(123)
        assert result["pj_ocr_columns"] == {"desc_pj": []}

    @patch("schema_utils.get_pj_ocr_columns")
    def test_pas_d_appel_sans_pj(self, mock_natures, mock_request):
        mock_request.return_value = _mock_graphql_response(
            {"data": {"demarche": _text_demarche()}}
        )

        result = get_demarche_schema(123)

        mock_natures.assert_not_called()
        assert "pj_ocr_columns" not in result

    def test_erreur_de_permissions_ignoree(self, mock_request):
        """Une erreur GraphQL de permissions n'empêche pas de lire le schéma"""
        mock_request.return_value = _mock_graphql_response(
            {
                "data": {"demarche": _text_demarche()},
                "errors": [{"message": "hidden due to permissions"}],
            }
        )

        result = get_demarche_schema(123)

        assert result["title"] == "Test démarche"

    def test_autre_erreur_graphql_leve_une_exception(self, mock_request):
        mock_request.return_value = _mock_graphql_response(
            {"data": None, "errors": [{"message": "Demarche introuvable"}]}
        )

        with pytest.raises(Exception, match="Demarche introuvable"):
            get_demarche_schema(123)

    def test_demarche_absente_leve_une_exception(self, mock_request):
        mock_request.return_value = _mock_graphql_response({"data": {"demarche": None}})

        with pytest.raises(Exception, match="Aucune donnée de démarche"):
            get_demarche_schema(123)

    def test_revision_active_absente_leve_une_exception(self, mock_request):
        mock_request.return_value = _mock_graphql_response(
            {"data": {"demarche": {"title": "Test", "activeRevision": None}}}
        )

        with pytest.raises(Exception, match="Aucune révision active"):
            get_demarche_schema(123)

    def test_erreur_http_leve_une_exception(self, mock_request):
        response = _mock_graphql_response({})
        response.raise_for_status.side_effect = requests.HTTPError("500")
        mock_request.return_value = response

        with pytest.raises(requests.HTTPError):
            get_demarche_schema(123)

    def test_sans_token_leve_une_erreur(self, mock_request):
        with (
            patch("dn.client.API_TOKEN", ""),
            patch("schema_utils.API_TOKEN", ""),
            pytest.raises(ValueError),
        ):
            get_demarche_schema(123)

        mock_request.assert_not_called()
