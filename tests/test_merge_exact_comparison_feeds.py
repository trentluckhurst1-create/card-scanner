from scripts.merge_exact_comparison_feeds import merge_refresh_preserving_live


def _group(key: str, source_a: str, source_b: str, price: float = 100.0) -> dict:
    return {
        "comparison_key": key,
        "comparison_type": "EXACT_CARD",
        "store_count": 2,
        "listing_count": 2,
        "listings": [
            {"source": source_a, "external_id": f"{key}-a", "landed_aud": price},
            {"source": source_b, "external_id": f"{key}-b", "landed_aud": price + 10},
        ],
    }


def test_missing_fresh_group_is_preserved():
    previous = {"comparison_groups": [_group("keep", "a", "b")], "market_cards": []}
    fresh = {"comparison_groups": [], "market_cards": [], "metrics": {}}

    merged = merge_refresh_preserving_live(previous, fresh)

    assert [g["comparison_key"] for g in merged["comparison_groups"]] == ["keep"]
    assert merged["metrics"]["previous_groups_lost"] == 0
    assert merged["metrics"]["retained_previous_groups_missing_from_fresh"] == 1


def test_fresh_same_key_replaces_previous_version():
    previous = {"comparison_groups": [_group("same", "a", "b", 100.0)], "market_cards": []}
    fresh = {"comparison_groups": [_group("same", "a", "b", 80.0)], "market_cards": [], "metrics": {}}

    merged = merge_refresh_preserving_live(previous, fresh)

    assert len(merged["comparison_groups"]) == 1
    assert merged["comparison_groups"][0]["listings"][0]["landed_aud"] == 80.0
    assert merged["metrics"]["fresh_exact_groups"] == 1


def test_new_fresh_group_is_added_without_deleting_old_group():
    previous = {"comparison_groups": [_group("old", "a", "b")], "market_cards": []}
    fresh = {"comparison_groups": [_group("new", "c", "d")], "market_cards": [], "metrics": {}}

    merged = merge_refresh_preserving_live(previous, fresh)

    assert {g["comparison_key"] for g in merged["comparison_groups"]} == {"old", "new"}
    assert merged["metrics"]["exact_comparison_groups"] == 2
    assert merged["governance"]["transient_refresh_group_deletion_allowed"] is False
