from card_scanner.cross_store_diagnostics import (
    build_reference_funnel,
    diagnose_reference_rejections,
    summarize_reference_rejections,
)
from card_scanner.cross_store_reference import build_cross_store_reference
from card_scanner.identity import parse_identity
from card_scanner.market_reference import MarketReferenceStatus
from card_scanner.models import Listing


def listing(
    source: str,
    external_id: str,
    title: str,
    *,
    price: float = 100.0,
    currency: str = "AUD",
) -> Listing:
    return Listing(
        source=source,
        external_id=external_id,
        url=f"https://example.invalid/{source}/{external_id}",
        title=title,
        sport="NBA",
        price=price,
        currency=currency,
        shipping=0.0,
        identity=parse_identity(title, "NBA"),
    )


def test_diagnostics_surface_card_number_and_serial_mismatches():
    candidate = listing(
        "cherry",
        "c1",
        "2024-25 Panini Prizm Example Player Silver #10 /99",
    )
    wrong_card = listing(
        "urbanempire",
        "u1",
        "2024/25 Panini Prizm Example Player Silver #11 /99",
    )
    wrong_serial = listing(
        "gimko",
        "g1",
        "2024/25 Panini Prizm Example Player Silver #10 /49",
    )

    summary = summarize_reference_rejections(
        diagnose_reference_rejections(
            candidate,
            [
                wrong_card,
                wrong_serial,
            ],
        )
    )

    assert summary["CARD_NUMBER_MISMATCH"] == 1
    assert summary["SERIAL_DENOMINATOR_MISMATCH"] == 1
    assert "YEAR_MISMATCH" not in summary


def test_diagnostics_surface_same_store_and_same_item_exclusions():
    candidate = listing(
        "cherry",
        "c1",
        "2024-25 Panini Prizm Example Player Silver #10",
    )
    same_item = candidate
    same_store_other = listing(
        "cherry",
        "c2",
        "2024/25 Panini Prizm Example Player Silver #10",
    )

    summary = summarize_reference_rejections(
        diagnose_reference_rejections(
            candidate,
            [
                same_item,
                same_store_other,
            ],
        )
    )

    assert summary["SAME_ITEM"] == 1
    assert summary["SAME_STORE"] == 2


def test_diagnostics_surface_year_parallel_and_grading_mismatches():
    candidate = listing(
        "cherry",
        "c1",
        "2024-25 Panini Prizm Example Player Red White Blue #10 PSA 10",
    )
    reference = listing(
        "urbanempire",
        "u1",
        "2025-26 Panini Prizm Example Player Silver Prizm #10 BGS 9",
    )

    summary = summarize_reference_rejections(
        diagnose_reference_rejections(
            candidate,
            [reference],
        )
    )

    assert summary["YEAR_MISMATCH"] == 1
    assert summary["PARALLEL_MISMATCH"] == 1
    assert summary["GRADER_MISMATCH"] == 1
    assert summary["GRADE_MISMATCH"] == 1


def test_diagnostics_do_not_create_reference_points():
    candidate = listing(
        "cherry",
        "c1",
        "2024-25 Panini Prizm Example Player Red White Blue #10",
    )
    reference = listing(
        "urbanempire",
        "u1",
        "2024/25 Panini Prizm Example Player Silver Prizm #10",
    )

    diagnostics = diagnose_reference_rejections(
        candidate,
        [reference],
    )
    cross_store_reference = build_cross_store_reference(
        candidate,
        [reference],
    )

    assert diagnostics
    assert cross_store_reference.status is MarketReferenceStatus.NO_REFERENCE
    assert cross_store_reference.matched_listing_count == 0


def test_diagnostics_surface_rookie_mismatch():
    candidate = listing(
        "cherry",
        "c1",
        "2024-25 Panini Prizm Example Player Rookie Silver #10",
    )
    reference = listing(
        "urbanempire",
        "u1",
        "2024-25 Panini Prizm Example Player Silver #10",
    )

    summary = summarize_reference_rejections(
        diagnose_reference_rejections(
            candidate,
            [reference],
        )
    )

    assert summary["ROOKIE_MISMATCH"] == 1


def test_reference_funnel_normalizes_season_years():
    candidate = listing(
        "cherry",
        "c1",
        "2024-25 Panini Prizm Example Player Silver Prizm #10 /99 PSA 10",
    )
    reference = listing(
        "urbanempire",
        "u1",
        "2024/25 Panini Prizm Example Player Silver Prizm #10 /99 PSA 10",
    )

    funnel = build_reference_funnel(candidate, [reference])

    assert funnel["CROSS_STORE"] == 1
    assert funnel["IDENTITY_PRESENT"] == 1
    assert funnel["SAME_PLAYER"] == 1
    assert funnel["SAME_YEAR"] == 1
    assert funnel["SAME_PRODUCT"] == 1
    assert funnel["SAME_CARD_NUMBER"] == 1
    assert funnel["SAME_PARALLEL"] == 1
    assert funnel["SAME_SERIAL"] == 1
    assert funnel["SAME_ROOKIE"] == 1
    assert funnel["SAME_AUTO_MEM"] == 1
    assert funnel["SAME_GRADING"] == 1
    assert funnel["EXACT_STRONG"] == 1


def test_reference_funnel_is_monotonic_and_surfaces_dropoff():
    candidate = listing(
        "cherry",
        "c1",
        "2024-25 Panini Prizm Example Player Silver Prizm #10 /99 PSA 10",
    )
    exact = listing(
        "urbanempire",
        "u1",
        "2024/25 Panini Prizm Example Player Silver Prizm #10 /99 PSA 10",
    )
    wrong_year = listing(
        "gimko",
        "g1",
        "2025-26 Panini Prizm Example Player Silver Prizm #10 /99 PSA 10",
    )
    wrong_card = listing(
        "sportscardstore",
        "s1",
        "2024/25 Panini Prizm Example Player Silver Prizm #11 /99 PSA 10",
    )
    wrong_player = listing(
        "urbanempire",
        "u2",
        "2024/25 Panini Prizm Different Player Silver Prizm #10 /99 PSA 10",
    )

    funnel = build_reference_funnel(
        candidate,
        [
            exact,
            wrong_year,
            wrong_card,
            wrong_player,
        ],
    )

    ordered = [
        "CROSS_STORE",
        "IDENTITY_PRESENT",
        "SAME_PLAYER",
        "SAME_YEAR",
        "SAME_PRODUCT",
        "SAME_CARD_NUMBER",
        "SAME_PARALLEL",
        "SAME_SERIAL",
        "SAME_ROOKIE",
        "SAME_AUTO_MEM",
        "SAME_GRADING",
        "EXACT_STRONG",
    ]

    values = [funnel[stage] for stage in ordered]

    assert all(
        left >= right
        for left, right in zip(values, values[1:])
    )
    assert funnel["CROSS_STORE"] == 4
    assert funnel["SAME_PLAYER"] == 3
    assert funnel["SAME_YEAR"] == 2
    assert funnel["SAME_CARD_NUMBER"] == 1
    assert funnel["EXACT_STRONG"] == 1


def test_reference_funnel_excludes_same_store_and_deduplicates_items():
    candidate = listing(
        "cherry",
        "c1",
        "2024-25 Panini Prizm Example Player Silver Prizm #10 /99 PSA 10",
    )
    same_store = listing(
        "cherry",
        "c2",
        "2024/25 Panini Prizm Example Player Silver Prizm #10 /99 PSA 10",
    )
    other_store = listing(
        "urbanempire",
        "u1",
        "2024/25 Panini Prizm Example Player Silver Prizm #10 /99 PSA 10",
    )

    funnel = build_reference_funnel(
        candidate,
        [
            same_store,
            other_store,
            other_store,
        ],
    )

    assert funnel["CROSS_STORE"] == 1
    assert funnel["EXACT_STRONG"] == 1


def test_reference_funnel_missing_precision_identity_stops_progression():
    candidate = listing(
        "cherry",
        "c1",
        "2024-25 Panini Prizm Example Player Silver Prizm #10",
    )
    missing_card_number = listing(
        "urbanempire",
        "u1",
        "2024/25 Panini Prizm Example Player Silver Prizm",
    )

    funnel = build_reference_funnel(
        candidate,
        [missing_card_number],
    )

    assert funnel["CROSS_STORE"] == 1
    assert funnel["IDENTITY_PRESENT"] == 1
    assert funnel["SAME_PLAYER"] == 1
    assert funnel["SAME_YEAR"] == 1
    assert funnel["SAME_PRODUCT"] == 1
    assert funnel["SAME_CARD_NUMBER"] == 0
    assert funnel["SAME_PARALLEL"] == 0
    assert funnel["EXACT_STRONG"] == 0


def test_reference_funnel_requires_known_serial_evidence():
    candidate = listing(
        source="cherry",
        external_id="serial-unknown-left",
        title="2024-25 Panini Prizm Example Player Silver Prizm #10 PSA 10",
    )
    reference = listing(
        source="urbanempire",
        external_id="serial-unknown-right",
        title="2024/25 Panini Prizm Example Player Silver Prizm #10 PSA 10",
    )

    funnel = build_reference_funnel(candidate, [reference])

    assert funnel["SAME_PARALLEL"] == 1
    assert funnel["SAME_SERIAL"] == 0
    assert funnel["SAME_ROOKIE"] == 0
    assert funnel["SAME_AUTO_MEM"] == 0
    assert funnel["SAME_GRADING"] == 0
    assert funnel["EXACT_STRONG"] == 0


def test_reference_funnel_known_equal_serial_denominator_survives():
    candidate = listing(
        source="cherry",
        external_id="serial-known-left",
        title="2024-25 Panini Prizm Example Player Silver Prizm #10 12/99 PSA 10",
    )
    reference = listing(
        source="urbanempire",
        external_id="serial-known-right",
        title="2024/25 Panini Prizm Example Player Silver Prizm #10 44/99 PSA 10",
    )

    funnel = build_reference_funnel(candidate, [reference])

    assert funnel["SAME_PARALLEL"] == 1
    assert funnel["SAME_SERIAL"] == 1
    assert funnel["SAME_ROOKIE"] == 1
    assert funnel["SAME_AUTO_MEM"] == 1
    assert funnel["SAME_GRADING"] == 1
    assert funnel["EXACT_STRONG"] == 1
