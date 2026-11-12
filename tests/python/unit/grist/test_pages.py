import json

from grist.pages import (
    get_folded_page_actions,
    is_demarche_table,
    get_page_attachment_actions,
    get_parent_page_name,
    get_parent_table_id,
)


def page(page_id, view_ref, indentation, page_pos):
    return {
        "id": page_id,
        "fields": {
            "viewRef": view_ref,
            "indentation": indentation,
            "pagePos": page_pos,
            "options": "",
        },
    }


def table(table_id, primary_view_id):
    return {
        "id": primary_view_id,
        "fields": {"tableId": table_id, "primaryViewId": primary_view_id},
    }


def tree_after(actions):
    """(id de page, indentation) dans l'ordre réécrit par BulkUpdateRecord."""
    [[name, table_id, page_ids, columns]] = actions
    assert name == "BulkUpdateRecord"
    assert table_id == "_grist_Pages"
    assert columns["pagePos"] == list(range(1, len(page_ids) + 1))
    return list(zip(page_ids, columns["indentation"]))


class TestNames:
    def test_parent_table_id(self):
        assert get_parent_table_id(12345) == "Demarche_12345"

    def test_parent_page_name(self):
        assert get_parent_page_name(12345) == "N° 12345"


class TestIsDemarcheTable:
    def test_table_of_the_demarche(self):
        assert is_demarche_table("Demarche_12345_dossiers", 12345)

    def test_case_insensitive(self):
        assert is_demarche_table("demarche_12345_champs", 12345)

    def test_parent_table_excluded(self):
        """la table parente n'est pas une table de données de la démarche"""
        assert not is_demarche_table("Demarche_12345", 12345)

    def test_other_demarche_sharing_a_prefix(self):
        """Demarche_123 ne doit pas capter les tables de Demarche_1234"""
        assert not is_demarche_table("Demarche_1234_dossiers", 123)

    def test_unrelated_table(self):
        assert not is_demarche_table("Sync_metadata", 12345)


class TestFoldedPageActions:
    def test_replaces_page_by_folded_one_at_same_place(self):
        """page retirée puis recréée pliée sur la même vue, et renommée"""
        pages = [page(1, 10, 0, 1), page(2, 20, 0, 2)]
        tables = [table("Autre", 10), table("Demarche_5", 20)]

        actions = get_folded_page_actions(pages, tables, "Demarche_5", "N° 5")

        assert actions == [
            ["RemoveRecord", "_grist_Pages", 2],
            [
                "AddRecord",
                "_grist_Pages",
                None,
                {
                    "viewRef": 20,
                    "indentation": 0,
                    "pagePos": 2,
                    "options": json.dumps({"collapsed": True}),
                },
            ],
            ["UpdateRecord", "_grist_Views", 20, {"name": "N° 5"}],
        ]

    def test_table_without_page(self):
        """table sans page (ou inconnue) -> aucune action"""
        pages = [page(1, 10, 0, 1)]
        tables = [table("Demarche_5", 20)]

        assert get_folded_page_actions(pages, tables, "Demarche_5", "N° 5") == []
        assert get_folded_page_actions(pages, tables, "Inconnue", "N° 5") == []


class TestPageAttachmentActions:
    def test_first_child_right_after_parent(self):
        """première synchro : la page enfant, créée en bas, suit la parente"""
        pages = [page(1, 1, 0, 1), page(2, 2, 0, 2), page(3, 3, 0, 3)]
        tables = [
            table("OTP", 1),
            table("Demarche_5", 2),
            table("Demarche_5_dossiers", 3),
        ]

        actions = get_page_attachment_actions(
            pages, tables, "Demarche_5", "Demarche_5_dossiers"
        )

        assert tree_after(actions) == [(1, 0), (2, 0), (3, 1)]

    def test_child_after_last_existing_child(self):
        """la nouvelle page passe après les enfants déjà présents"""
        pages = [page(1, 1, 0, 1), page(2, 2, 1, 2), page(3, 3, 0, 3)]
        tables = [
            table("Demarche_5", 1),
            table("Demarche_5_dossiers", 2),
            table("Demarche_5_champs", 3),
        ]

        actions = get_page_attachment_actions(
            pages, tables, "Demarche_5", "Demarche_5_champs"
        )

        assert tree_after(actions) == [(1, 0), (2, 1), (3, 1)]

    def test_parent_in_the_middle(self):
        """table créée lors d'une synchro ultérieure : la page remonte sous sa
        parente au lieu de devenir l'enfant de la dernière page"""
        pages = [
            page(1, 1, 0, 1),  # N° 5
            page(2, 2, 1, 2),  #   dossiers
            page(3, 3, 0, 3),  # N° 6
            page(4, 4, 1, 4),  #   dossiers
            page(5, 5, 0, 5),  # Sync_metadata
            page(6, 6, 0, 6),  # Demarche_5_avis, créée en bas
        ]
        tables = [
            table("Demarche_5", 1),
            table("Demarche_5_dossiers", 2),
            table("Demarche_6", 3),
            table("Demarche_6_dossiers", 4),
            table("Sync_metadata", 5),
            table("Demarche_5_avis", 6),
        ]

        actions = get_page_attachment_actions(
            pages, tables, "Demarche_5", "Demarche_5_avis"
        )

        assert tree_after(actions) == [(1, 0), (2, 1), (6, 1), (3, 0), (4, 1), (5, 0)]

    def test_user_subpages_kept(self):
        """sous-pages de l'utilisateur sous un enfant : la page passe après elles,
        les autres pages gardent leur indentation"""
        pages = [
            page(1, 1, 0, 1),  # N° 5
            page(2, 2, 1, 2),  #   dossiers
            page(3, 7, 2, 3),  #     page de l'utilisateur
            page(4, 8, 0, 4),  # page de l'utilisateur
            page(5, 5, 0, 5),  # Demarche_5_champs, créée en bas
        ]
        tables = [
            table("Demarche_5", 1),
            table("Demarche_5_dossiers", 2),
            table("Demarche_5_champs", 5),
        ]

        actions = get_page_attachment_actions(
            pages, tables, "Demarche_5", "Demarche_5_champs"
        )

        assert tree_after(actions) == [(1, 0), (2, 1), (3, 2), (5, 1), (4, 0)]

    def test_order_follows_page_pos(self):
        """l'ordre lu est celui de pagePos, pas celui des enregistrements"""
        pages = [page(3, 3, 0, 3), page(1, 1, 0, 1), page(2, 2, 0, 2)]
        tables = [
            table("Demarche_5", 1),
            table("Autre", 2),
            table("Demarche_5_dossiers", 3),
        ]

        actions = get_page_attachment_actions(
            pages, tables, "Demarche_5", "Demarche_5_dossiers"
        )

        assert tree_after(actions) == [(1, 0), (3, 1), (2, 0)]

    def test_missing_parent_page(self):
        """page parente supprimée par l'utilisateur -> aucune action"""
        pages = [page(1, 1, 0, 1)]
        tables = [table("Demarche_5", 9), table("Demarche_5_dossiers", 1)]

        assert (
            get_page_attachment_actions(
                pages, tables, "Demarche_5", "Demarche_5_dossiers"
            )
            == []
        )

    def test_missing_child_page(self):
        pages = [page(1, 1, 0, 1)]
        tables = [table("Demarche_5", 1), table("Demarche_5_dossiers", 0)]

        assert (
            get_page_attachment_actions(
                pages, tables, "Demarche_5", "Demarche_5_dossiers"
            )
            == []
        )
