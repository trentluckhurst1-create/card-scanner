from card_scanner.identity import parse_identity
from card_scanner.year_catalog import (
    MultiYearCatalogResolver,
    YearCatalogProvider,
)
from card_scanner.year_resolution import YearEvidence


def target():
    return parse_identity(
        "Victor Wembanyama Panini Select #87 Blue Prizm PSA 10",
        "NBA",
    )


def row(source, year="2023", parallel="Blue"):
    return YearEvidence(
        source=source,
        year=year,
        player="Victor Wembanyama",
        set_name="Panini Select",
        card_number="87",
        parallel=parallel,
    )


class FakeProvider(YearCatalogProvider):
    def __init__(self, name, rows=None, error=None):
        self.name = name
        self.rows = list(rows or [])
        self.error = error
        self.calls = 0

    def lookup_year_evidence(self, sport, identity):
        self.calls += 1
        if self.error:
            raise self.error
        return list(self.rows)


def test_two_independent_catalog_providers_resolve():
    a = FakeProvider(
        "sportscardspro",
        [row("sportscardspro")],
    )
    b = FakeProvider(
        "hobbyscan",
        [row("hobbyscan")],
    )

    result = MultiYearCatalogResolver([a, b]).resolve(
        "NBA", target()
    )

    assert result.resolution.status == "RESOLVED"
    assert result.resolution.year == "2023"
    assert result.evidence_count == 2
    assert result.providers_succeeded == (
        "sportscardspro", "hobbyscan"
    )


def test_one_provider_is_insufficient():
    a = FakeProvider(
        "sportscardspro",
        [row("sportscardspro")],
    )

    result = MultiYearCatalogResolver([a]).resolve(
        "NBA", target()
    )

    assert result.resolution.status == "INSUFFICIENT_EVIDENCE"
    assert result.resolution.year is None


def test_duplicate_rows_from_one_provider_do_not_resolve():
    a = FakeProvider(
        "sportscardspro",
        [
            row("sportscardspro"),
            row("sportscardspro"),
        ],
    )

    result = MultiYearCatalogResolver([a]).resolve(
        "NBA", target()
    )

    assert result.resolution.status == "INSUFFICIENT_EVIDENCE"
    assert result.resolution.year is None


def test_provider_failure_is_isolated():
    bad = FakeProvider(
        "broken",
        error=RuntimeError("boom"),
    )
    a = FakeProvider("catalog_a", [row("catalog_a")])
    b = FakeProvider("catalog_b", [row("catalog_b")])

    result = MultiYearCatalogResolver(
        [bad, a, b]
    ).resolve("NBA", target())

    assert result.resolution.status == "RESOLVED"
    assert result.resolution.year == "2023"
    assert result.providers_considered == (
        "broken", "catalog_a", "catalog_b"
    )
    assert result.providers_succeeded == (
        "catalog_a", "catalog_b"
    )
    assert result.provider_errors == (
        "broken: RuntimeError",
    )


def test_conflicting_providers_fail_closed():
    a = FakeProvider(
        "catalog_a",
        [row("catalog_a", year="2023")],
    )
    b = FakeProvider(
        "catalog_b",
        [row("catalog_b", year="2024")],
    )

    result = MultiYearCatalogResolver([a, b]).resolve(
        "NBA", target()
    )

    assert result.resolution.status == "CONFLICT"
    assert result.resolution.year is None


def test_wrong_parallel_does_not_create_consensus():
    a = FakeProvider(
        "catalog_a",
        [row("catalog_a", parallel="Light Blue")],
    )
    b = FakeProvider(
        "catalog_b",
        [row("catalog_b", parallel="Light Blue")],
    )

    result = MultiYearCatalogResolver([a, b]).resolve(
        "NBA", target()
    )

    assert result.resolution.status == "INSUFFICIENT_EVIDENCE"
    assert result.resolution.year is None


def test_provider_cannot_impersonate_another_source():
    a = FakeProvider(
        "catalog_a",
        [row("catalog_b")],
    )
    b = FakeProvider(
        "catalog_b",
        [row("catalog_b")],
    )

    result = MultiYearCatalogResolver([a, b]).resolve(
        "NBA", target()
    )

    assert result.evidence_count == 1
    assert result.resolution.status == "INSUFFICIENT_EVIDENCE"


def test_minimum_source_count_cannot_be_lowered_below_two():
    a = FakeProvider("catalog_a", [row("catalog_a")])

    resolver = MultiYearCatalogResolver(
        [a],
        min_independent_sources=1,
    )

    result = resolver.resolve("NBA", target())

    assert resolver.min_independent_sources == 2
    assert result.resolution.status == "INSUFFICIENT_EVIDENCE"


def test_existing_year_remains_authoritative():
    known = parse_identity(
        "Victor Wembanyama 2023 Panini Select #87 Blue Prizm PSA 10",
        "NBA",
    )

    a = FakeProvider(
        "catalog_a",
        [row("catalog_a", year="2024")],
    )
    b = FakeProvider(
        "catalog_b",
        [row("catalog_b", year="2024")],
    )

    result = MultiYearCatalogResolver([a, b]).resolve(
        "NBA", known
    )

    assert result.resolution.status == "ALREADY_KNOWN"
    assert result.resolution.year == "2023"
