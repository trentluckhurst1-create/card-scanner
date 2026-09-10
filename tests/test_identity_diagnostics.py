from __future__ import annotations

from card_scanner.identity_diagnostics import build_identity_diagnostics, family_identity_gaps
from card_scanner.market_catalogue import MarketListingObservation
from card_scanner.models import CardIdentity, Listing


def _listing(source: str, external_id: str, identity: CardIdentity | None) -> Listing:
    return Listing(
        source=source,
        external_id=external_id,
        url=f"https://example.com/{external_id}",
        title=f"Card {external_id}",
        sport="NFL",
        price=100.0,
        currency="AUD",
        identity=identity,
    )


def test_family_identity_gaps_reports_missing_fields_without_relaxing_matching():
    row = MarketListingObservation(
        listing=_listing(
            "cherry",
            "1",
            CardIdentity(
                sport="NFL",
                player="Player One",
                year="2025",
                brand="Topps",
            ),
        )
    )

    assert family_identity_gaps(row) == ("MISSING_STRUCTURED_DISCRIMINATOR",)


def test_identity_diagnostics_counts_gap_reasons_and_source_eligibility():
    rows = [
        MarketListingObservation(
            listing=_listing(
                "cherry",
                "1",
                CardIdentity(
                    sport="NFL",
                    player="Player One",
                    year="2025",
                    brand="Topps",
                    card_number="10",
                ),
            )
        ),
        MarketListingObservation(
            listing=_listing(
                "cherry",
                "2",
                CardIdentity(sport="NFL", player="Player Two", year="2025", brand="Topps"),
            )
        ),
        MarketListingObservation(listing=_listing("gimko", "3", None)),
    ]

    result = build_identity_diagnostics(rows)

    assert result["listing_count"] == 3
    assert result["family_eligible_count"] == 1
    assert result["family_ineligible_count"] == 2
    assert result["gap_counts"] == {
        "MISSING_STRUCTURED_DISCRIMINATOR": 1,
        "NO_IDENTITY": 1,
    }
    assert result["interpretation"] == "DIAGNOSTIC_ONLY_DOES_NOT_RELAX_MATCHING_OR_VALUATION_GATES"

    by_source = {row["source"]: row for row in result["by_source"]}
    assert by_source["cherry"]["listing_count"] == 2
    assert by_source["cherry"]["family_eligible_count"] == 1
    assert by_source["gimko"]["family_eligible_count"] == 0
