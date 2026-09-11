from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "audit_live_comparisons.py"
    spec = importlib.util.spec_from_file_location("audit_live_comparisons_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _card(source: str, external_id: str, price: float, *, set_name: str) -> dict:
    return {
        "source": source,
        "external_id": external_id,
        "url": f"https://example.test/{external_id}",
        "title": "Test card",
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
            "card_number": "#043" if source == "cherry" else "43",
            "parallel": "Silver",
            "serial_total": None,
            "grader": None,
            "grade": None,
            "rookie": True,
            "autograph": False,
            "memorabilia": False,
        },
        "card_family": {"key": "legacy-different-key" if source == "cherry" else "other-legacy-key"},
    }


def test_live_audit_recomputes_v2_family_keys_before_comparing():
    module = _load_module()
    feed = {
        "generated_at": "2026-09-11T00:00:00+00:00",
        "market_cards": [
            _card("cherry", "a", 100.0, set_name="Topps Chrome"),
            _card("gimko", "b", 125.0, set_name="Chrome"),
        ],
    }
    audit = module.build_audit(feed)
    assert audit["market_cards"] == 2
    assert audit["family_keys_recomputed"] == 2
    assert audit["exact_match_count"] == 1
    assert audit["comparison_group_count"] == 1
    assert audit["top_groups"][0]["cheapest_store"] == "cherry"
    assert audit["top_groups"][0]["saving_vs_highest_aud"] == 25.0
    assert audit["governance"]["can_create_buy"] is False
