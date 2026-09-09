from copy import deepcopy

from card_scanner.identity import parse_identity
from card_scanner.models import SoldComp
from card_scanner.sold_comp_engine import assess_strict_sold_comp
from card_scanner.year_resolution import YearEvidence, resolve_year


def target():
    return parse_identity(
        "Victor Wembanyama 2023 Panini Select #87 Blue Prizm PSA 10",
        "NBA",
    )


def renaiss_identity_without_year():
    return parse_identity(
        "Victor Wembanyama Panini Select #87 Blue Prizm PSA 10",
        "NBA",
    )


def catalog_evidence(source, year="2023", parallel="Blue"):
    return YearEvidence(
        source=source,
        year=year,
        player="Victor Wembanyama",
        set_name="Panini Select",
        card_number="87",
        parallel=parallel,
    )


def comp_with_identity(identity):
    return SoldComp(
        source="renaiss_transaction",
        sale_id="renaiss-sale-1",
        sold_date="2026-09-07",
        title="Victor Wembanyama Panini Select #87 Blue Prizm PSA 10",
        sold_price=150.0,
        currency="USD",
        shipping=0.0,
        sold_price_aud=225.0,
        sale_type="transaction",
        url=None,
        notes="YEAR_RESOLUTION_RESEARCH",
        identity=identity,
    )


def enrich_year(identity, year):
    enriched = deepcopy(identity)
    enriched.year = year
    return enriched


def test_unresolved_renaiss_comp_fails_strict_matcher():
    source = target()
    candidate = renaiss_identity_without_year()

    match = assess_strict_sold_comp(
        "target-listing",
        source,
        comp_with_identity(candidate),
    )

    assert match.match_level.value == "REJECT"
    assert "candidate year missing" in match.rejection_reasons


def test_two_catalogs_resolve_year_then_strict_matcher_accepts():
    source = target()
    candidate = renaiss_identity_without_year()

    resolution = resolve_year(
        candidate,
        [
            catalog_evidence("sportscardspro"),
            catalog_evidence("hobbyscan"),
        ],
    )

    assert resolution.status == "RESOLVED"
    assert resolution.year == "2023"

    enriched = enrich_year(candidate, resolution.year)

    assert candidate.year is None
    assert enriched.year == "2023"

    match = assess_strict_sold_comp(
        "target-listing",
        source,
        comp_with_identity(enriched),
    )

    assert match.match_level.value in {"EXACT", "STRONG"}
    assert match.match_score >= 0.70


def test_single_catalog_cannot_unlock_strict_acceptance():
    candidate = renaiss_identity_without_year()

    resolution = resolve_year(
        candidate,
        [catalog_evidence("sportscardspro")],
    )

    assert resolution.status == "INSUFFICIENT_EVIDENCE"
    assert resolution.year is None

    match = assess_strict_sold_comp(
        "target-listing",
        target(),
        comp_with_identity(candidate),
    )

    assert match.match_level.value == "REJECT"


def test_conflicting_catalog_years_cannot_unlock_acceptance():
    candidate = renaiss_identity_without_year()

    resolution = resolve_year(
        candidate,
        [
            catalog_evidence("catalog_a", year="2023"),
            catalog_evidence("catalog_b", year="2024"),
        ],
    )

    assert resolution.status == "CONFLICT"
    assert resolution.year is None

    match = assess_strict_sold_comp(
        "target-listing",
        target(),
        comp_with_identity(candidate),
    )

    assert match.match_level.value == "REJECT"


def test_parallel_disagreement_cannot_resolve_year():
    candidate = renaiss_identity_without_year()

    resolution = resolve_year(
        candidate,
        [
            catalog_evidence("catalog_a", parallel="Light Blue"),
            catalog_evidence("catalog_b", parallel="Light Blue"),
        ],
    )

    assert resolution.status == "INSUFFICIENT_EVIDENCE"
    assert resolution.year is None


def test_resolution_does_not_mutate_original_identity():
    candidate = renaiss_identity_without_year()

    resolution = resolve_year(
        candidate,
        [
            catalog_evidence("catalog_a"),
            catalog_evidence("catalog_b"),
        ],
    )

    assert resolution.status == "RESOLVED"

    enriched = enrich_year(candidate, resolution.year)

    assert candidate.year is None
    assert enriched.year == "2023"
