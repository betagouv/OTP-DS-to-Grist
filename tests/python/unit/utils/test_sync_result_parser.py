from utils.sync_result_parser import parse_success_count, parse_error_count


class TestParseSuccessCount:
    def test_format_simple_returns_count(self):
        result = parse_success_count("Dossiers traités avec succès: 10")
        assert result == (10, None)

    def test_format_with_total(self):
        result = parse_success_count("Dossiers traités avec succès: 8/15")
        assert result == (8, 15)

    def test_no_match_returns_none(self):
        result = parse_success_count("Progression: 50 - Finalisation")
        assert result == (None, None)

    def test_invalid_format_returns_none(self):
        result = parse_success_count("Dossiers traités avec succès:")
        assert result == (None, None)


class TestParseErrorCount:
    def test_valid_format_returns_count(self):
        result = parse_error_count("Dossiers en échec: 3")
        assert result == 3

    def test_no_match_returns_none(self):
        result = parse_error_count("Progression: 50 - Finalisation")
        assert result is None

    def test_empty_value_returns_none(self):
        result = parse_error_count("Dossiers en échec:")
        assert result is None

    def test_invalid_format_returns_none(self):
        result = parse_error_count("Dossiers en échec: abc")
        assert result is None
