from card_scanner.cross_store_diagnostics import (
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
