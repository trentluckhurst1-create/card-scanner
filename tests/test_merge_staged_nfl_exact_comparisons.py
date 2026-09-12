from scripts.merge_staged_nfl_exact_comparisons import merge_additive_nfl_exact


def _card(source: str, external_id: str, family_key: str) -> dict:
    return {
        "source": source,
        "external_id": external_id,
        "url": f"https://example.test/{external_id}",
        "title": "2025 Topps Chrome Test Player #10 Silver",
        "sport": "NFL",
        "asking_price": 100.0,
        "shipping": 0.0,
        "currency": "AUD",
        "landed_aud": 100.0,
        "identity": {
            "player": "Test Player",
            "year": "2025",
            "brand": "Topps",
            "set_name": "Topps Chrome",
            "card_number": "10",
            "parallel": "Silver",
            "serial_total": None,
            "grader": None,
            "grade": None,
            "rookie": False,
            "autograph": False,
            "memorabilia": False,
        },
        "card_family": {
            "key": family_key,
            "eligible": True,
            "match_rule": "STRICT_STRUCTURED_IDENTITY",
            "match_confidence": 1.0,
        },
    }


def test_additive_merge_never_deletes_existing_production_groups():
    existing = {
        "comparison_key": "existing-key",
        "comparison_type": "EXACT_CARD",
        "store_count": 2,
        "listing_count": 2,
        "listings": [
            {"source": "a", "external_id": "1"},
            {"source": "b", "external_id": "2"},
        ],
    }
    production = {
        "feed_type": "EXACT_CARD_STORE_COMPARISON_ONLY",
        "governance": {"exact_card_only": True},
        "metrics": {"exact_comparison_groups": 1, "exact_comparison_listings": 2},
        "market_cards": [],
        "comparison_groups": [existing],
    }
    staging = {
        "market_cards": [
            _card("cherry", "c1", "nfl-family-1"),
            _card("ebay", "e1", "nfl-family-1"),
        ]
    }

    merged = merge_additive_nfl_exact(production, staging)

    assert existing in merged["comparison_groups"]
    assert merged["metrics"]["production_groups_before_nfl_merge"] == 1
    assert merged["metrics"]["production_groups_lost"] == 0
    assert merged["metrics"]["staged_nfl_groups_added"] == 1
    assert merged["metrics"]["exact_comparison_groups"] == 2
    assert merged["governance"]["production_group_deletion_allowed"] is False


def test_existing_key_wins_collision_and_is_not_duplicated():
    staged_cards = [
        _card("cherry", "c1", "same-family"),
        _card("ebay", "e1", "same-family"),
    ]
    # Build once to discover the exact guarded comparison key.
    seed = merge_additive_nfl_exact(
        {"market_cards": [], "comparison_groups": [], "metrics": {}},
        {"market_cards": staged_cards},
    )
    key = seed["comparison_groups"][0]["comparison_key"]
    existing = {
        "comparison_key": key,
        "comparison_type": "EXACT_CARD",
        "store_count": 2,
        "listing_count": 2,
        "listings": [],
    }
    production = {"market_cards": [], "comparison_groups": [existing], "metrics": {}}

    merged = merge_additive_nfl_exact(production, {"market_cards": staged_cards})

    assert merged["metrics"]["staged_nfl_groups_added"] == 0
    assert merged["comparison_groups"] == [existing]
