from card_scanner.identity import parse_identity
from card_scanner.year_resolution import (
    YearEvidence,
    evidence_matches_identity,
    resolve_year,
)


def target_without_year():
    return parse_identity(
        "Victor Wembanyama Panini Select #87 Blue Prizm PSA 10",
        "NBA",
    )


def evidence(source, year="2023", parallel="Blue"):
    return YearEvidence(
        source=source,
        year=year,
        player="Victor Wembanyama",
        set_name="Panini Select",
        card_number="87",
        parallel=parallel,
    )


def test_exact_identity_evidence_matches():
    assert evidence_matches_identity(
        target_without_year(),
        evidence("catalog_a"),
    )


def test_wrong_player_rejected():
    item = evidence("catalog_a")
    item = YearEvidence(
        source=item.source,
        year=item.year,
        player="Different Player",
        set_name=item.set_name,
        card_number=item.card_number,
        parallel=item.parallel,
    )
    assert not evidence_matches_identity(
        target_without_year(), item
    )


def test_wrong_card_number_rejected():
    item = evidence("catalog_a")
    item = YearEvidence(
        source=item.source,
        year=item.year,
        player=item.player,
        set_name=item.set_name,
        card_number="7",
        parallel=item.parallel,
    )
    assert not evidence_matches_identity(
        target_without_year(), item
    )


def test_wrong_parallel_rejected():
    assert not evidence_matches_identity(
        target_without_year(),
        evidence("catalog_a", parallel="Light Blue"),
    )


def test_missing_parallel_rejected():
    assert not evidence_matches_identity(
        target_without_year(),
        evidence("catalog_a", parallel=None),
    )


def test_one_source_cannot_resolve_year():
    result = resolve_year(
        target_without_year(),
        [evidence("catalog_a")],
    )
    assert result.status == "INSUFFICIENT_EVIDENCE"
    assert result.year is None


def test_duplicate_same_source_does_not_count_twice():
    result = resolve_year(
        target_without_year(),
        [evidence("catalog_a"), evidence("catalog_a")],
    )
    assert result.status == "INSUFFICIENT_EVIDENCE"
    assert result.year is None


def test_two_independent_sources_resolve_same_year():
    result = resolve_year(
        target_without_year(),
        [
            evidence("sportscardspro"),
            evidence("hobbyscan"),
        ],
    )
    assert result.status == "RESOLVED"
    assert result.year == "2023"
    assert set(result.accepted_sources) == {
        "sportscardspro",
        "hobbyscan",
    }


def test_conflicting_years_fail_closed():
    result = resolve_year(
        target_without_year(),
        [
            evidence("catalog_a", year="2023"),
            evidence("catalog_b", year="2024"),
        ],
    )
    assert result.status == "CONFLICT"
    assert result.year is None


def test_invalid_year_rejected():
    result = resolve_year(
        target_without_year(),
        [
            evidence("catalog_a", year="23"),
            evidence("catalog_b", year="23"),
        ],
    )
    assert result.status == "INSUFFICIENT_EVIDENCE"
    assert result.year is None


def test_existing_target_year_is_never_overwritten():
    target = parse_identity(
        "Victor Wembanyama 2023 Panini Select #87 Blue Prizm PSA 10",
        "NBA",
    )
    result = resolve_year(
        target,
        [
            evidence("catalog_a", year="2024"),
            evidence("catalog_b", year="2024"),
        ],
    )
    assert result.status == "ALREADY_KNOWN"
    assert result.year == "2023"
