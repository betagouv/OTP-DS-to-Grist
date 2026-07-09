import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..")
)


def make_champ(label, typename, descriptor_id, value=None, checked=None, selected=None):
    """Fabrique un champ DS minimal."""
    champ = {
        "__typename": typename,
        "id": f"id_{descriptor_id}",
        "champDescriptorId": descriptor_id,
        "label": label,
        "updatedAt": "2024-01-01T00:00:00Z",
        "prefilled": False,
    }
    if typename == "TextChamp":
        champ["stringValue"] = value or ""
    elif typename == "CheckboxChamp":
        champ["checked"] = checked if checked is not None else False
    elif typename == "YesNoChamp":
        champ["selected"] = selected
    return champ


def make_dossier(champs, annotations=None):
    """Fabrique un dossier DS minimal."""
    return {
        "id": "dossier_1",
        "number": 1,
        "state": "accepte",
        "dateDepot": "2024-01-01T00:00:00Z",
        "dateDerniereModification": "2024-01-01T00:00:00Z",
        "dateDerniereModificationChamps": None,
        "dateDerniereModificationAnnotations": None,
        "datePassageEnConstruction": None,
        "datePassageEnInstruction": None,
        "dateExpiration": None,
        "dateTraitement": None,
        "dateSuppressionParUsager": None,
        "dateAccuseLectureAgreement": None,
        "labels": [],
        "champs": champs,
        "annotations": annotations or [],
        "avis": [],
        "usager": {"email": "test@test.fr"},
        "demandeur": None,
        "prenomMandataire": "",
        "nomMandataire": "",
        "deposeParUnTiers": False,
    }


class TestDuplicateLabelSuffixes:
    def _get_labels(self, dossier, descriptor_to_column_id=None):
        """Retourne la liste des labels produits par dossier_to_flat_data."""
        from queries_extract import dossier_to_flat_data

        flat = dossier_to_flat_data(
            dossier,
            exclude_repetition_champs=True,
            descriptor_to_column_id=descriptor_to_column_id,
        )
        return [item["label"] for item in flat["champs"]]

    def test_no_duplicate_no_suffix(self):
        """Un champ unique ne doit pas être suffixé."""
        dossier = make_dossier(
            [
                make_champ("Nom", "TextChamp", "desc_001", value="Martin"),
            ]
        )
        labels = self._get_labels(dossier)
        assert "Nom" in labels
        assert "Nom_1" not in labels

    def test_two_duplicates_get_suffixes(self):
        """Deux champs avec le même label → premier sans suffixe, second avec _1."""
        dossier = make_dossier(
            [
                make_champ("Nom", "TextChamp", "desc_001", value="Martin"),
                make_champ("Nom", "TextChamp", "desc_002", value="Dupont"),
            ]
        )
        labels = self._get_labels(dossier)
        assert "Nom" in labels
        assert "Nom_1" in labels

    def test_suffix_stable_regardless_of_order(self):
        """
        Le suffixe doit être basé sur champDescriptorId, pas sur l'ordre.
        Le mapping descriptor_to_column_id (issu du schéma DS) garantit
        que desc_001 → "Nom" et desc_002 → "Nom_1" quel que soit l'ordre.
        """
        from queries_extract import dossier_to_flat_data

        descriptor_to_column_id = {
            "desc_001": "Nom",
            "desc_002": "Nom_1",
        }

        dossier_a = make_dossier(
            [
                make_champ("Nom", "TextChamp", "desc_001", value="Martin"),
                make_champ("Nom", "TextChamp", "desc_002", value="Dupont"),
            ]
        )
        flat_a = dossier_to_flat_data(
            dossier_a,
            exclude_repetition_champs=True,
            descriptor_to_column_id=descriptor_to_column_id,
        )
        labels_a = {item["label"]: item["value"] for item in flat_a["champs"]}

        dossier_b = make_dossier(
            [
                make_champ("Nom", "TextChamp", "desc_002", value="Dupont"),
                make_champ("Nom", "TextChamp", "desc_001", value="Martin"),
            ]
        )
        flat_b = dossier_to_flat_data(
            dossier_b,
            exclude_repetition_champs=True,
            descriptor_to_column_id=descriptor_to_column_id,
        )
        labels_b = {item["label"]: item["value"] for item in flat_b["champs"]}

        assert labels_a.get("Nom") == "Martin"
        assert labels_b.get("Nom") == "Martin"
        assert labels_a.get("Nom_1") == "Dupont"
        assert labels_b.get("Nom_1") == "Dupont"

    def test_three_duplicates(self):
        """Trois champs identiques → Nom, Nom_1, Nom_2."""
        dossier = make_dossier(
            [
                make_champ("Nom", "TextChamp", "desc_001", value="A"),
                make_champ("Nom", "TextChamp", "desc_002", value="B"),
                make_champ("Nom", "TextChamp", "desc_003", value="C"),
            ]
        )
        labels = self._get_labels(dossier)
        assert "Nom" in labels
        assert "Nom_1" in labels
        assert "Nom_2" in labels

    def test_different_labels_not_affected(self):
        """Des champs avec des labels différents ne doivent pas être suffixés."""
        dossier = make_dossier(
            [
                make_champ("Nom", "TextChamp", "desc_001", value="Martin"),
                make_champ("Prénom", "TextChamp", "desc_002", value="Jean"),
            ]
        )
        labels = self._get_labels(dossier)
        assert "Nom" in labels
        assert "Prénom" in labels
        assert "Nom_1" not in labels
        assert "Prénom_1" not in labels

    def test_annotation_duplicates(self):
        """Les annotations en doublon doivent aussi être gérées stablement."""
        from queries_extract import dossier_to_flat_data

        dossier = make_dossier(
            champs=[],
            annotations=[
                make_champ("Avis", "TextChamp", "desc_010", value="OK"),
                make_champ("Avis", "TextChamp", "desc_011", value="KO"),
            ],
        )
        flat = dossier_to_flat_data(dossier, exclude_repetition_champs=True)
        labels = [item["label"] for item in flat["annotations"]]
        assert "annotation_Avis" in labels
        assert "annotation_Avis_1" in labels
