from datetime import datetime, timedelta, timezone

from database.models import SyncLog
from sync.incremental import (
    SinceDates,
    dates_from_env,
    dates_to_env,
    dates_to_request,
    needs_full_sync,
    next_dates_to_request,
)

FILTERS_KEY = '{"date_debut": null}'
DEMARCHE = "12345"
DATE = "2024-01-01T00:00:00Z"
DATE_UTC = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _previous(**overrides):
    """Synchro précédente de la même démarche, filtres inchangés, qui a laissé
    des dates."""
    fields = {
        "demarche_number": DEMARCHE,
        "filters_hash": FILTERS_KEY,
        "modified_dossiers_since": DATE_UTC,
        "deleted_dossiers_since": DATE_UTC,
    }
    fields.update(overrides)
    return SyncLog(**fields)


class TestNeedsFullSync:
    def test_no_previous_sync(self):
        assert needs_full_sync(None, DEMARCHE, FILTERS_KEY) is True

    def test_same_demarche_and_filters_is_incremental(self):
        assert needs_full_sync(_previous(), DEMARCHE, FILTERS_KEY) is False

    def test_demarche_number_compared_as_text(self):
        """`sync_logs.demarche_number` est du texte, la configuration peut
        porter un entier."""
        assert needs_full_sync(_previous(), int(DEMARCHE), FILTERS_KEY) is False

    def test_changed_demarche(self):
        assert needs_full_sync(_previous(), "67890", FILTERS_KEY) is True

    def test_changed_filters(self):
        previous = _previous(filters_hash="anciens_filtres")

        assert needs_full_sync(previous, DEMARCHE, FILTERS_KEY) is True

    def test_forced_despite_previous_dates(self):
        assert needs_full_sync(_previous(), DEMARCHE, FILTERS_KEY, forced=True) is True

    def test_missing_filters_hash(self):
        """Synchro enregistrée sans `filters_hash` : synchro complète ponctuelle."""
        assert (
            needs_full_sync(_previous(filters_hash=None), DEMARCHE, FILTERS_KEY) is True
        )


class TestDatesToRequest:
    def test_incremental_sync_keeps_previous_dates(self):
        previous = _previous(deleted_dossiers_since=DATE_UTC - timedelta(days=1))

        assert dates_to_request(previous, full_sync=False) == SinceDates(
            modified_dossiers_since=DATE,
            deleted_dossiers_since="2023-12-31T00:00:00Z",
        )

    def test_full_sync_has_no_dates(self):
        assert dates_to_request(_previous(), full_sync=True) == SinceDates()

    def test_no_previous_sync_has_no_dates(self):
        assert dates_to_request(None, full_sync=False) == SinceDates()

    def test_missing_deleted_date(self):
        """Vérification des suppressions jamais aboutie : pas de date pour elles."""
        previous = _previous(deleted_dossiers_since=None)

        assert dates_to_request(previous, full_sync=False) == SinceDates(
            modified_dossiers_since=DATE
        )

    def test_date_converted_to_utc(self):
        """Date relue à l'heure de Paris (fuseau de la base) : transmise en UTC."""
        paris = timezone(timedelta(hours=1))
        previous = _previous(
            modified_dossiers_since=datetime(2024, 1, 1, 1, tzinfo=paris)
        )

        assert (
            dates_to_request(previous, full_sync=False).modified_dossiers_since == DATE
        )


class TestDatesEnvironment:
    def test_round_trip(self):
        dates = SinceDates(
            modified_dossiers_since=DATE, deleted_dossiers_since="2023-12-31T00:00:00Z"
        )

        assert dates_from_env(dates_to_env(dates)) == dates

    def test_no_dates_round_trip(self):
        assert dates_to_env(SinceDates()) == {
            "MODIFIED_DOSSIERS_SINCE": "",
            "DELETED_DOSSIERS_SINCE": "",
        }
        assert dates_from_env(dates_to_env(SinceDates())) == SinceDates()

    def test_missing_variables_mean_no_dates(self):
        assert dates_from_env({}) == SinceDates()


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
