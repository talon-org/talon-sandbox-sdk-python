import pytest
from talon_sandbox._parse import parse_size, parse_duration


# ─── parse_size ───────────────────────────────────────────────────────────────

class TestParseSize:
    def test_bytes_bare_int(self) -> None:
        assert parse_size(1024) == 1024

    def test_bytes_string(self) -> None:
        assert parse_size("1024") == 1024

    def test_kib(self) -> None:
        assert parse_size("1KiB") == 1024

    def test_mib(self) -> None:
        assert parse_size("1MiB") == 1024 ** 2

    def test_gib(self) -> None:
        assert parse_size("4GiB") == 4 * 1024 ** 3

    def test_tib(self) -> None:
        assert parse_size("1TiB") == 1024 ** 4

    def test_kb_si(self) -> None:
        assert parse_size("1KB") == 1000

    def test_mb_si(self) -> None:
        assert parse_size("1MB") == 1_000_000

    def test_gb_si(self) -> None:
        assert parse_size("1GB") == 1_000_000_000

    def test_case_insensitive(self) -> None:
        assert parse_size("4gib") == 4 * 1024 ** 3
        assert parse_size("4GIB") == 4 * 1024 ** 3

    def test_float_value(self) -> None:
        assert parse_size("1.5GiB") == int(1.5 * 1024 ** 3)

    def test_invalid_unit(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse size"):
            parse_size("4XiB")

    def test_empty_string(self) -> None:
        with pytest.raises(ValueError):
            parse_size("")

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValueError):
            parse_size("-1GiB")

    def test_float_bytes(self) -> None:
        assert parse_size(1024.0) == 1024


# ─── parse_duration ───────────────────────────────────────────────────────────

class TestParseDuration:
    def test_seconds_int(self) -> None:
        assert parse_duration(30) == 30

    def test_seconds_bare_string(self) -> None:
        assert parse_duration("30") == 30

    def test_seconds_suffix(self) -> None:
        assert parse_duration("30s") == 30

    def test_minutes(self) -> None:
        assert parse_duration("5m") == 300

    def test_hours(self) -> None:
        assert parse_duration("2h") == 7200

    def test_days(self) -> None:
        assert parse_duration("1d") == 86400

    def test_weeks(self) -> None:
        assert parse_duration("1w") == 7 * 86400

    def test_milliseconds(self) -> None:
        assert parse_duration("500ms") == 0  # rounds down to 0 whole seconds

    def test_float(self) -> None:
        assert parse_duration("1.5h") == 5400

    def test_invalid_unit(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse duration"):
            parse_duration("1y")

    def test_empty_string(self) -> None:
        with pytest.raises(ValueError):
            parse_duration("")

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValueError):
            parse_duration("-5m")

    def test_float_seconds(self) -> None:
        assert parse_duration(30.9) == 30

    def test_30m(self) -> None:
        assert parse_duration("30m") == 1800

    def test_6h(self) -> None:
        assert parse_duration("6h") == 21600
