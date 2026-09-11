from __future__ import annotations

from card_scanner.active_price_comparison import (
    EXACT_MATCH,
    PLAYER_YEAR_MARKET,
    SAME_PRODUCT_VARIANTS,
    build_active_price_comparisons,
)


def card(
    source: str,
    external_id: str,
    price: float,
    *,
    player: str = "Test Player",
    year: str = "2025",
    product: str = "Topps Chrome",
    family_key: str | None = None,
    card_number: str | None = "10",
    parallel: str | None = "Silver",
) -> dict:
    return {
        "source": source,
        "external_id": external_id,
        "url": f"https://example.test/{external_id}",
        "title": f"{year} {product} {player}",
        "sport": "NFL",
        "asking_price": price,
        "shipping": 0.0,
        "currency": "AUD",
        "landed_aud": price,
        "identity": {
            "player": player,
            "year": year,
            "brand": "Topps",
            "set_name": product,
            "card_number": card_number,
            "parallel": parallel,
            "serial_total": None,
            "grader": None,
            "grade": None,
            "rookie": False,
            "autograph": False,
            "memorabilia": False,
        },
        "card_family": {
            "key": family_key,
            "eligible": family_key is not None,
            "match_rule": "STRICT_STRUCTURED_IDENTITY",
        },
    }


def test_exact_match_reports_cheapest_store_and_real_savings_without_calling_it_value():
    result = build_active_price_comparisons(
        [
            card("cherry", "a", 100.0, family_key="cf_same"),
            card("gimko", "b", 125.0, family_key="cf_same"),
            card("urbanempire", "c", 140.0, family_key="cf_same"),
        ]
    )

    assert result["exact_match_count"] == 1
    group = result["groups"][0]
    assert group["comparison_type"] == EXACT_MATCH
    assert group["exact_equivalent"] is True
    assert group["cheapest_store"] == "cherry"
    assert group["cheapest_landed_aud"] == 100.0
    assert group["next_best_store"] == "gimko"
    assert group["saving_vs_next_best_aud"] == 25.0
    assert group["saving_vs_next_best_pct"] == 20.0
    assert group["saving_vs_median_aud"] == 25.0
    assert group["saving_vs_highest_aud"] == 40.0
    assert group["spread_pct"] == 40.0
    assert group["pricing_basis"] == "ACTIVE_ASKS_ONLY_NOT_FAIR_VALUE"
    assert result["governance"]["can_create_buy"] is False
    assert "fair_value" not in repr(group).casefold()


def test_same_product_variants_are_grouped_but_explicitly_not_exact_equivalents():
    result = build_active_price_comparisons(
        [
            card("cherry", "a", 90.0, family_key="cf_a", parallel="Silver"),
            card("gimko", "b", 110.0, family_key="cf_b", parallel="Gold"),
        ]
    )

    assert result["exact_match_count"] == 0
    assert result["same_product_variant_count"] == 1
    group = result["groups"][0]
    assert group["comparison_type"] == SAME_PRODUCT_VARIANTS
    assert group["exact_equivalent"] is False
    assert "NOT GUARANTEED" in group["comparison_warning"]
    assert group["cheapest_store"] == "cherry"
    assert group["saving_vs_highest_aud"] == 20.0


def test_player_year_market_is_last_resort_and_never_claimed_as_same_card():
    result = build_active_price_comparisons(
        [
            card("cherry", "a", 75.0, product="Topps Chrome", family_key="cf_a"),
            card("gimko", "b", 130.0, product="Panini Prizm", family_key="cf_b"),
        ]
    )

    assert result["same_product_variant_count"] == 0
    assert result["player_year_market_count"] == 1
    group = result["groups"][0]
    assert group["comparison_type"] == PLAYER_YEAR_MARKET
    assert group["exact_equivalent"] is False
    assert group["cheapest_store"] == "cherry"
    assert group["spread_aud"] == 55.0


def test_single_store_never_creates_cross_store_comparison():
    result = build_active_price_comparisons(
        [
            card("cherry", "a", 100.0, family_key="cf_same"),
            card("cherry", "b", 90.0, family_key="cf_same"),
        ]
    )

    assert result["comparison_group_count"] == 0
    assert result["groups"] == []


def test_exact_members_are_not_duplicated_into_related_groups():
    result = build_active_price_comparisons(
        [
            card("cherry", "a", 100.0, family_key="cf_same"),
            card("gimko", "b", 125.0, family_key="cf_same"),
            card("urbanempire", "c", 140.0, family_key="cf_other", parallel="Gold"),
        ]
    )

    assert result["exact_match_count"] == 1
    assert result["same_product_variant_count"] == 0
    assert result["player_year_market_count"] == 0
    assert result["comparison_group_count"] == 1
