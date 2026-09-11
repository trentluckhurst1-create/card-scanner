from scripts.publish_exact_comparisons import build_exact_comparison_feed


def _group(kind, stores=2, listings=None):
    return {
        "comparison_type": kind,
        "store_count": stores,
        "listings": listings or [],
    }


def test_exact_feed_excludes_non_exact_groups_and_subsets_cards():
    exact_listings = [
        {"source": "cherry", "external_id": "1"},
        {"source": "urbanempire", "external_id": "2"},
    ]
    payload = {
        "generated_at": "2026-09-11T00:00:00Z",
        "metrics": {"active_cards": 3},
        "market_cards": [
            {"source": "cherry", "external_id": "1", "title": "Exact A"},
            {"source": "urbanempire", "external_id": "2", "title": "Exact A"},
            {"source": "boop", "external_id": "3", "title": "Different card"},
        ],
        "active_price_comparisons": {
            "groups": [
                _group("EXACT_CARD", 2, exact_listings),
                _group("SAME_PRODUCT_VARIANTS", 2, [{"source": "boop", "external_id": "3"}]),
                _group("PLAYER_YEAR_MARKET", 2, [{"source": "boop", "external_id": "3"}]),
                _group("EXACT_CARD", 1, [{"source": "boop", "external_id": "3"}]),
            ]
        },
    }

    result = build_exact_comparison_feed(payload)

    assert result["feed_type"] == "EXACT_CARD_STORE_COMPARISON_ONLY"
    assert result["metrics"]["active_cards_scanned"] == 3
    assert result["metrics"]["exact_comparison_groups"] == 1
    assert result["metrics"]["exact_comparison_listings"] == 2
    assert len(result["comparison_groups"]) == 1
    assert result["comparison_groups"][0]["comparison_type"] == "EXACT_CARD"
    assert {(row["source"], row["external_id"]) for row in result["market_cards"]} == {
        ("cherry", "1"),
        ("urbanempire", "2"),
    }
    assert result["governance"]["exact_card_only"] is True
    assert result["governance"]["related_variants_included"] is False
    assert result["governance"]["player_year_context_included"] is False
    assert result["governance"]["active_asks_are_fair_value"] is False
    assert result["governance"]["can_create_buy"] is False


def test_exact_feed_is_valid_when_no_exact_matches_exist():
    result = build_exact_comparison_feed({
        "generated_at": "2026-09-11T00:00:00Z",
        "metrics": {"active_cards": 2917},
        "market_cards": [{"source": "boop", "external_id": "1"}],
        "active_price_comparisons": {"groups": [_group("SAME_PRODUCT_VARIANTS", 2)]},
    })

    assert result["metrics"]["active_cards_scanned"] == 2917
    assert result["metrics"]["exact_comparison_groups"] == 0
    assert result["metrics"]["exact_comparison_listings"] == 0
    assert result["comparison_groups"] == []
    assert result["market_cards"] == []
