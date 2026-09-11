from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_stage7_scan_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "stage7_scan.py"
    spec = importlib.util.spec_from_file_location("stage7_scan_test_module", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _card(source: str, external_id: str, price: float, family_key: str) -> dict:
    return {
        "source": source,
        "external_id": external_id,
        "url": f"https://example.test/{external_id}",
        "title": f"2025 Topps Chrome Test Player #{external_id}",
        "sport": "NFL",
        "asking_price": price,
        "shipping": 0.0,
        "currency": "AUD",
        "landed_aud": price,
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
        },
    }


def test_stage7_publisher_adds_governed_price_comparison_contract(tmp_path):
    module = _load_stage7_scan_module()
    output = tmp_path / "market.json"
    output.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "metrics": {},
                "market_cards": [
                    _card("cherry", "a", 100.0, "cf_same"),
                    _card("gimko", "b", 125.0, "cf_same"),
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = module._publish_active_price_comparisons(output)

    comparisons = payload["active_price_comparisons"]
    assert comparisons["comparison_group_count"] == 1
    assert comparisons["exact_match_count"] == 1
    assert comparisons["governance"]["active_asks_are_fair_value"] is False
    assert comparisons["governance"]["can_create_buy"] is False
    assert payload["metrics"]["price_comparison_groups"] == 1
    assert payload["metrics"]["exact_price_comparison_groups"] == 1

    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted == payload
    assert "fair_value" not in repr(comparisons).casefold()
