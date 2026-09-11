from __future__ import annotations

from card_scanner.identity_diagnostics import build_identity_diagnostics, family_identity_gaps
from card_scanner.market_catalogue import MarketListingObservation
from card_scanner.models import CardIdentity, Listing


def _listing(
    source: str,
    external_id: str,
    identity: CardIdentity | None,
    *,
    title: str | None = None,
) -> Listing:
    return Listing(
        source=source,
        external_id=external_id,
        url=f"https://example.com/{external_id}",
        title=title or f"Card {external_id}",
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


def test_identity_diagnostics_separates_family_eligibility_from_sold_readiness():
    rows = [
        # Family eligible and sold-research ready: quality = .70 exactly.
        MarketListingObservation(
            listing=_listing(
                "cherry",
                "ready",
                CardIdentity(
                    sport="NFL",
                    player="Player One",
                    year="2025",
                    brand="Topps",
                    card_number="10",
                    autograph=True,
                    rookie=True,
                ),
                title="2025 Topps PLAYER ONE Rookie Auto #10",
            )
        ),
        # Family eligible but below sold threshold: player .30 + year .10 +
        # brand .15 + card number .10 = .65.
        MarketListingObservation(
            listing=_listing(
                "cherry",
                "family-only",
                CardIdentity(
                    sport="NFL",
                    player="Player Two",
                    year="2025",
                    brand="Topps",
                    card_number="11",
                ),
                title="2025 Topps PLAYER TWO #11",
            )
        ),
        MarketListingObservation(
            listing=_listing(
                "gimko",
                "missing-discriminator",
                CardIdentity(
                    sport="NFL",
                    player="Player Three",
                    year="2025",
                    brand="Topps",
                ),
                title="2025 Topps PLAYER THREE",
            )
        ),
        MarketListingObservation(listing=_listing("gimko", "no-identity", None)),
    ]

    result = build_identity_diagnostics(rows)

    assert result["listing_count"] == 4
    assert result["family_eligible_count"] == 2
    assert result["family_ineligible_count"] == 2
    assert result["sold_identity_quality_threshold"] == 0.70
    assert result["sold_research_ready_count"] == 1
    assert result["sold_research_not_ready_count"] == 3
    assert result["sold_research_ready_pct"] == 25.0
    assert result["sold_not_ready_reason_counts"]["IDENTITY_BELOW_SOLD_THRESHOLD"] == 3
    assert result["sold_not_ready_reason_counts"]["NO_IDENTITY"] == 1
    assert result["gap_counts"] == {
        "MISSING_STRUCTURED_DISCRIMINATOR": 1,
        "NO_IDENTITY": 1,
    }
    assert result["identity_quality_bands"]["0_60_TO_0_69"] == 1
    assert result["identity_quality_bands"]["0_70_PLUS"] == 1
    assert result["interpretation"] == "DIAGNOSTIC_ONLY_DOES_NOT_RELAX_MATCHING_OR_VALUATION_GATES"

    by_source = {row["source"]: row for row in result["by_source"]}
    assert by_source["cherry"]["family_eligible_count"] == 2
    assert by_source["cherry"]["sold_research_ready_count"] == 1
    assert by_source["cherry"]["sold_research_not_ready_count"] == 1
    assert by_source["gimko"]["family_eligible_count"] == 0
    assert by_source["gimko"]["sold_research_ready_count"] == 0


def test_non_card_product_is_diagnostic_not_ready_without_relaxing_gate():
    row = MarketListingObservation(
        listing=_listing(
            "gimko",
            "bundle",
            CardIdentity(
                sport="NFL",
                player="Player Four",
                year="2025",
                brand="Topps",
                card_number="12",
                parallel="Gold",
                serial_total=50,
            ),
            title="2025 Topps Player Four Gold #12 /50 Full Team Set Bundle",
        )
    )

    result = build_identity_diagnostics([row])

    assert result["family_eligible_count"] == 1
    assert result["sold_research_ready_count"] == 0
    assert result["sold_not_ready_reason_counts"]["NON_CARD_PRODUCT"] == 1
    assert result["interpretation"] == "DIAGNOSTIC_ONLY_DOES_NOT_RELAX_MATCHING_OR_VALUATION_GATES"
