from __future__ import annotations

from card_scanner.active_price_comparison import build_active_price_comparisons


def card(source: str, external_id: str, price: float, *, family_key: str | None, set_name: str = "Topps Chrome") -> dict:
    return {
        "source": source,
        "external_id": external_id,
        "url": f"https://example.test/{external_id}",
        "title": f"2025 {set_name} Test Player #43 Silver",
        "sport": "NFL",
        "asking_price": price,
        "shipping": 0.0,
        "currency": "AUD",
        "landed_aud": price,
        "identity": {
            "player": "Test Player",
            "year": "2025",
            "brand": "Topps",
            "set_name": set_name,
            "card_number": "43",
            "parallel": "Silver",
            "serial_total": None,
            "grader": None,
            "grade": None,
            "rookie": True,
            "autograph": False,
            "memorabilia": False,
        },
        "card_family": {
            "key": family_key,
            "eligible": family_key is not None,
            "match_rule": "STRICT_STRUCTURED_IDENTITY_V2",
            "match_confidence": 1.0 if family_key else None,
            "match_reasons": ["same player", "same year", "same brand/product", "same card number", "same parallel"] if family_key else [],
        },
    }


def test_exact_comparison_exports_full_confidence_and_reasons():
    result = build_active_price_comparisons([
        card("cherry", "a", 100.0, family_key="cf_same"),
        card("gimko", "b", 120.0, family_key="cf_same"),
    ])
    group = result["groups"][0]
    assert group["comparison_type"] == "EXACT_CARD"
    assert group["match_confidence"] == 1.0
    assert "same card number" in group["match_reasons"]
    assert "same parallel" in group["match_reasons"]


def test_same_product_variant_comparison_is_lower_confidence_and_explicitly_non_exact():
    a = card("cherry", "a", 100.0, family_key="cf_a")
    b = card("gimko", "b", 120.0, family_key="cf_b")
    result = build_active_price_comparisons([a, b])
    group = result["groups"][0]
    assert group["comparison_type"] == "SAME_PRODUCT_VARIANTS"
    assert group["match_confidence"] == 0.65
    assert "variant fields may differ" in group["match_reasons"]
    assert group["exact_equivalent"] is False
