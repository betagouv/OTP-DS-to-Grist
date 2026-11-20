from sync.incremental import (
    SinceDates,
    dates_to_request,
    needs_full_sync,
    next_dates_to_request,
)

FILTERS_KEY = '{"date_debut": null}'
DATE = "2024-01-01T00:00:00Z"


def _previous(**overrides):
    """État laissé par une synchro précédente réussie, filtres inchangés."""
    previous = {
        "updated_since_cursor": DATE,
        "deleted_since_cursor": DATE,
        "force_full_sync": False,
        "filters_hash": FILTERS_KEY,
    }
    previous.update(overrides)
    return previous


class TestNeedsFullSync:
    def test_no_previous_state(self):
        assert needs_full_sync(None, FILTERS_KEY) is True

    def test_unchanged_filters_is_incremental(self):
        assert needs_full_sync(_previous(), FILTERS_KEY) is False

    def test_requested_full_sync(self):
        assert needs_full_sync(_previous(force_full_sync=True), FILTERS_KEY) is True

    def test_changed_filters(self, capsys):
        previous = _previous(filters_hash="anciens_filtres")

        assert needs_full_sync(previous, FILTERS_KEY) is True
        assert "Changement de filtres détecté" in capsys.readouterr().out

    def test_missing_filters_hash(self):
        """État antérieur à `filters_hash` : synchro complète ponctuelle."""
        assert needs_full_sync(_previous(filters_hash=None), FILTERS_KEY) is True

    def test_missing_force_flag_is_incremental(self):
        previous = _previous()
        del previous["force_full_sync"]

        assert needs_full_sync(previous, FILTERS_KEY) is False


class TestDatesToRequest:
    def test_incremental_sync_keeps_previous_dates(self):
        previous = _previous(deleted_since_cursor="2023-12-31T00:00:00Z")

        assert dates_to_request(previous, full_sync=False) == SinceDates(
            modified_dossiers_since=DATE,
            deleted_dossiers_since="2023-12-31T00:00:00Z",
        )

    def test_full_sync_has_no_dates(self):
        assert dates_to_request(_previous(), full_sync=True) == SinceDates()

    def test_no_previous_state_has_no_dates(self):
        assert dates_to_request(None, full_sync=False) == SinceDates()

    def test_previous_state_without_dates(self):
        """Sans date enregistrée, la synchro demande tous les dossiers sans être
        déclarée complète (comportement existant)."""
        previous = _previous(updated_since_cursor=None, deleted_since_cursor=None)

        assert dates_to_request(previous, full_sync=False) == SinceDates()

    def test_numeric_updated_since_is_converted(self):
        """Colonne Grist en type DateTime : horodatage numérique (#284)."""
        previous = _previous(updated_since_cursor=1704067200)

        assert (
            dates_to_request(previous, full_sync=False).modified_dossiers_since == DATE
        )


class TestNextDatesToRequest:
    START = "2024-02-01T00:00:00Z"
    CURRENT = SinceDates(modified_dossiers_since=DATE, deleted_dossiers_since=DATE)

    def _next(self, current=CURRENT, dossiers_complete=True, deletions_checked=True):
        return next_dates_to_request(
            current,
            self.START,
            dossiers_complete=dossiers_complete,
            deletions_checked=deletions_checked,
        )

    def test_success_advances_both_dates(self):
        assert self._next() == SinceDates(
            modified_dossiers_since=self.START,
            deleted_dossiers_since=self.START,
        )

    def test_incomplete_dossiers_keep_both_dates(self):
        assert self._next(dossiers_complete=False) == self.CURRENT

    def test_failed_deletion_check_keeps_only_deleted_date(self):
        assert self._next(deletions_checked=False) == SinceDates(
            modified_dossiers_since=self.START,
            deleted_dossiers_since=DATE,
        )

    def test_full_sync_success_sets_dates(self):
        assert self._next(current=SinceDates()) == SinceDates(
            modified_dossiers_since=self.START,
            deleted_dossiers_since=self.START,
        )

    def test_incomplete_full_sync_leaves_no_dates(self):
        """Synchro complète inachevée : pas de date, la suivante sera complète."""
        assert self._next(current=SinceDates(), dossiers_complete=False) == SinceDates()
