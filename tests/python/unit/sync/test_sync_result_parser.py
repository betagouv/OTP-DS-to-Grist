from sync.sync_result_parser import (
    _parse_success_count,
    _parse_error_count,
    parse_output,
)

class TestParseSuccessCount:
    def test_format_simple_returns_count(self):
        result = _parse_success_count("Dossiers traités avec succès: 10")
        assert result == (10, None)

    def test_format_with_total(self):
        result = _parse_success_count("Dossiers traités avec succès: 8/15")
        assert result == (8, 15)

    def test_no_match_returns_none(self):
        result = _parse_success_count("Progression: 50 - Finalisation")
        assert result == (None, None)

    def test_invalid_format_returns_none(self):
        result = _parse_success_count("Dossiers traités avec succès:")
        assert result == (None, None)


class TestParseErrorCount:
    def test_valid_format_returns_count(self):
        result = _parse_error_count("Dossiers en échec: 3")
        assert result == 3

    def test_no_match_returns_none(self):
        result = _parse_error_count("Progression: 50 - Finalisation")
        assert result is None

    def test_empty_value_returns_none(self):
        result = _parse_error_count("Dossiers en échec:")
        assert result is None

    def test_invalid_format_returns_none(self):
        result = _parse_error_count("Dossiers en échec: abc")
        assert result is None


class TestParseOutput:
    def test_success_with_errors(self):
        lines = [
            "Dossiers traités avec succès: 85",
            "Dossiers en échec: 15",
            "Total dossiers traités: 100",
        ]
        result = parse_output(lines)
        assert result["success"] is False
        assert result["success_count"] == 85
        assert result["error_count"] == 15
        assert result["total_processed"] == 100
        assert result["dossier_count"] == 100
        assert "timestamp" in result

    def test_success_only(self):
        lines = ["Dossiers traités avec succès: 10"]
        result = parse_output(lines)
        assert result["success"] is True
        assert result["success_count"] == 10
        assert result["error_count"] == 0

    def test_already_up_to_date(self):
        lines = ["La base Grist est déjà à jour", "Aucun dossier modifié"]
        result = parse_output(lines)
        assert result["sync_reason"] == "already_up_to_date"
        assert result["success_count"] == 0
        assert result["error_count"] == 0

    def test_calcul_total_auto(self):
        lines = [
            "Dossiers traités avec succès: 5",
            "Dossiers en échec: 3",
        ]
        result = parse_output(lines)
        assert result["total_processed"] == 8

    def test_lignes_vides(self):
        lines = []
        result = parse_output(lines)
        assert result["success"] is True
        assert result["success_count"] == 0
        assert result["error_count"] == 0
        assert result["total_processed"] == 0


class TestParseOutputWithDetailedErrorLogs:
    """Les logs d'erreur détaillés (table, dossier) ne doivent pas fausser les
    compteurs, que `sync_result_parser` extrait de phrases précises."""

    def test_logs_detailles_laissent_intacts_les_compteurs(self):
        lignes = [
            "ERREUR: [DOSSIERS] 2 dossier(s) masqué(s) par les permissions : "
            "Dossier 2 hidden due to permissions",
            "ERREUR: Erreur lors de la création par lot de la table champs "
            "(20 dossiers): 413 - Request body too large",
            "ERREUR: Échec individuel pour le dossier 1001 (ligne Grist 5)",
            "ERREUR: Dossier 7 trop volumineux pour Grist (2000000 octets "
            "pour une limite de 1048576) : envoi tenté, il sera refusé",
            "ERREUR: Erreur préparation dossier 1002: champ illisible",
            "ERREUR: dossier_number ou number manquant dans les données "
            "(table champs, champs ['name']): l'enregistrement est ignoré",
            "Dossiers traités avec succès: 18",
            "Dossiers en échec: 2",
        ]
        result = parse_output(lignes)
        assert result["success_count"] == 18
        assert result["error_count"] == 2
        assert result["total_processed"] == 20
        assert result["success"] is False

    def test_phrase_reservee_avec_dossiers_ne_trompe_pas_le_parser(self):
        """Documente la contrainte : les phrases de bilan ne doivent porter que
        le nombre, sinon `parse_output` renverrait None et l'UI afficherait 0."""
        lignes = [
            "ERREUR: Dossiers en échec: 3 (dossiers 5, 7, 9)",
            "Dossiers traités avec succès: 18",
        ]
        result = parse_output(lignes)
        assert result["error_count"] == 0
