import pytest

import json
import re

from sync.sync_result_parser import (
    SYNC_ERRORS_PREFIX,
    SyncMetadataParseError,
    _parse_success_count,
    _parse_error_count,
    _parse_sync_metadata,
    emit_sync_errors,
    emit_sync_metadata,
    parse_output,
    read_sync_errors,
    timestamped_error,
)
from utils.log import MAX_SYNC_ERRORS


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

    def test_labels_deja_a_jour_ne_suffit_pas(self):
        """La ligne de rafraîchissement des labels contient « déjà à jour » mais
        ne signifie pas que le sync n'a rien eu à faire : un sync à 0 dossier
        (filtres restrictifs) ne doit pas être classé already_up_to_date."""
        lines = [
            "Dossiers traités avec succès: 0",
            "Sync complète — rafraîchissement des labels ignoré (déjà à jour).",
        ]
        result = parse_output(lines)
        assert result["sync_reason"] == "synced"

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


class TestSyncMetadataContract:
    """Contrat d'émission/parsing de la ligne SYNC_METADATA entre le pipeline
    (sous-processus) et le parent : durée, force_full_sync et empreinte des
    filtres. Absente → valeurs None. Présente mais illisible → SyncMetadataParseError
    en interne, signalée par le flag sync_metadata_error sans impacter les compteurs."""

    def test_emit_est_parsee_par_parse_output(self, capsys):
        emit_sync_metadata(12.5, True, '{"date_debut": "2024-01-01"}')
        captured = capsys.readouterr()
        assert captured.out.startswith("SYNC_METADATA: ")
        result = parse_output(captured.out.splitlines())
        assert result["duration_seconds"] == 12.5
        assert result["force_full_sync"] is True
        assert result["filters_hash"] == '{"date_debut": "2024-01-01"}'
        assert result["sync_metadata_error"] is False

    def test_emit_force_full_sync_false(self, capsys):
        emit_sync_metadata(3.0, False, "{}")
        result = parse_output(capsys.readouterr().out.splitlines())
        assert result["force_full_sync"] is False

    def test_metadata_absentes_sont_none(self):
        result = parse_output(["Dossiers traités avec succès: 10"])
        assert result["duration_seconds"] is None
        assert result["force_full_sync"] is None
        assert result["filters_hash"] is None
        assert result["sync_metadata_error"] is False

    def test_metadata_malformee_signalee_sans_casser_les_compteurs(self):
        lines = [
            "SYNC_METADATA: {pas-du-json",
            "Dossiers traités avec succès: 10",
            "Dossiers en échec: 2",
        ]
        result = parse_output(lines)
        assert result["duration_seconds"] is None
        assert result["force_full_sync"] is None
        assert result["filters_hash"] is None
        assert result["sync_metadata_error"] is True
        assert result["success_count"] == 10
        assert result["error_count"] == 2

    def test_metadata_non_dict_signalee(self):
        result = parse_output(["SYNC_METADATA: 42"])
        assert result["duration_seconds"] is None
        assert result["sync_metadata_error"] is True


class TestParseSyncMetadata:
    """`_parse_sync_metadata` est le contrat : pas mon préfixe → None ; mon
    préfixe mais illisible → SyncMetadataParseError (signal interne, attrapé
    par parse_output)."""

    def test_ligne_sans_prefixe_retourne_none(self):
        assert _parse_sync_metadata("Dossiers traités avec succès: 10") is None

    def test_ligne_valide_retourne_le_dict(self):
        metadata = _parse_sync_metadata('SYNC_METADATA: {"duration_seconds": 1.0}')
        assert metadata == {"duration_seconds": 1.0}

    def test_json_illisible_leve(self):
        with pytest.raises(SyncMetadataParseError):
            _parse_sync_metadata("SYNC_METADATA: {pas-du-json")

    def test_contenu_non_dict_leve(self):
        with pytest.raises(SyncMetadataParseError):
            _parse_sync_metadata("SYNC_METADATA: [1, 2]")


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


class TestTimestampedError:
    """Erreur horodatée à l'instant présent"""

    def test_horodatage_utc_a_la_milliseconde(self):
        error = timestamped_error("boom")

        assert error["message"] == "boom"
        assert re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", error["timestamp"]
        )


class TestSyncErrorsContract:
    """Émission de la ligne SYNC_ERRORS par le sous-processus : première erreur
    de chaque dossier en échec et erreurs générales, ignorée par parse_output."""

    @staticmethod
    def _emitted(capsys) -> dict:
        line = capsys.readouterr().out.strip()
        assert line.startswith(SYNC_ERRORS_PREFIX)
        return json.loads(line[len(SYNC_ERRORS_PREFIX):])

    def test_dossiers_dans_l_ordre_des_echecs_et_erreurs_generales(self, capsys):
        dossier_errors = {
            "7": {"timestamp": "2026-11-16T23:05:27.100Z", "message": "Création : 400"},
            "3": {"timestamp": "2026-11-16T23:05:27.200Z", "message": "Préparation"},
        }
        general = [{"timestamp": "2026-11-16T23:05:28.000Z", "message": "Labels"}]

        emit_sync_errors(dossier_errors, general)

        assert self._emitted(capsys) == {
            "dossiers": [
                {
                    "dossier": "7",
                    "timestamp": "2026-11-16T23:05:27.100Z",
                    "message": "Création : 400",
                },
                {
                    "dossier": "3",
                    "timestamp": "2026-11-16T23:05:27.200Z",
                    "message": "Préparation",
                },
            ],
            "dossiers_total": 2,
            "general": general,
        }

    def test_dossiers_bornes_erreurs_generales_non_bornees(self, capsys):
        """Au plus MAX_SYNC_ERRORS dossiers, les premiers en échec ; total conservé"""
        count = MAX_SYNC_ERRORS + 5
        dossier_errors = {
            str(number): {"timestamp": "t", "message": "m"} for number in range(count)
        }
        general = [{"timestamp": "t", "message": f"g{n}"} for n in range(count)]

        emit_sync_errors(dossier_errors, general)

        emitted = self._emitted(capsys)
        assert [d["dossier"] for d in emitted["dossiers"]] == [
            str(number) for number in range(MAX_SYNC_ERRORS)
        ]
        assert emitted["dossiers_total"] == count
        assert len(emitted["general"]) == count

    def test_rien_n_est_emis_sans_erreur(self, capsys):
        emit_sync_errors({}, [])

        assert capsys.readouterr().out == ""

    def test_accents_conserves(self, capsys):
        emit_sync_errors({}, [{"timestamp": "t", "message": "Échec réseau"}])

        assert "Échec réseau" in capsys.readouterr().out

    def test_ignoree_par_parse_output(self, capsys):
        """Une phrase de bilan dans un message ne modifie pas les compteurs"""
        emit_sync_errors(
            {"1": {"timestamp": "t", "message": "Dossiers en échec: 99"}},
            [{"timestamp": "t", "message": "Grist déjà à jour"}],
        )
        lines = capsys.readouterr().out.splitlines()

        result = parse_output(lines + ["Dossiers traités avec succès: 0"])

        assert result["error_count"] == 0
        assert result["sync_reason"] == "synced"


class TestReadSyncErrors:
    """Lecture de la ligne SYNC_ERRORS dans la sortie du sous-processus"""

    def test_relit_ce_qui_est_emis(self, capsys):
        dossier_errors = {"7": {"timestamp": "t1", "message": "Création : 400"}}
        general = [{"timestamp": "t2", "message": "Labels"}]
        emit_sync_errors(dossier_errors, general)
        lines = ["Dossiers en échec: 1"] + capsys.readouterr().out.splitlines()

        assert read_sync_errors(lines) == {
            "dossiers": [{"dossier": "7", "timestamp": "t1", "message": "Création : 400"}],
            "dossiers_total": 1,
            "general": general,
        }

    def test_ligne_absente_aucune_erreur(self):
        assert read_sync_errors(["Dossiers en échec: 1"]) == {
            "dossiers": [],
            "dossiers_total": 0,
            "general": [],
        }

    @pytest.mark.parametrize("payload", ["{pas du json", "[]"])
    def test_ligne_illisible_signalee_dans_general(self, payload):
        errors = read_sync_errors([SYNC_ERRORS_PREFIX + payload])

        assert errors["dossiers"] == []
        (error,) = errors["general"]
        assert "SYNC_ERRORS illisible" in error["message"]
        assert re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", error["timestamp"]
        )
