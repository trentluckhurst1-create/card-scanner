from __future__ import annotations

import json
from pathlib import Path

from scripts.stage7_scan import build_parser


def test_stage7_scan_defaults_to_persistent_history_and_market_feed(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["stage7_scan.py"],
    )
    args = build_parser().parse_args()

    assert args.source == "all"
    assert args.sport == "ALL"
    assert args.dashboard_json == "docs/market.json"
    assert args.no_record_history is False


def _all_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key).casefold()
            yield from _all_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _all_keys(child)


def test_market_feed_uses_governed_schema_without_raw_payload_keys():
    payload = json.loads(Path("docs/market.json").read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert isinstance(payload["cards"], list)
    assert payload["generated_at"] is None or isinstance(payload["generated_at"], str)
    assert not any(key.startswith("raw") for key in _all_keys(payload))
    assert any("not fair value" in rule for rule in payload["governance"])
    assert any("genuine sold evidence" in rule for rule in payload["governance"])

    for card in payload["cards"]:
        valuation = card["valuation"]
        research = card["research"]
        sold_evidence = card["sold_evidence"]

        assert research["can_create_buy"] is False
        assert "raw" not in sold_evidence

        if valuation["status"] != "VALUED":
            assert valuation["fair_value_aud"] is None
            assert valuation["edge_pct"] is None

        if card["opportunity_status"] in {"BUY", "STRONG_BUY"}:
            assert valuation["status"] == "VALUED"
            assert sold_evidence["accepted_count"] > 0


def test_live_dashboard_consumes_governed_market_feed():
    html = Path("docs/index.html").read_text(encoding="utf-8")

    assert "market.json?ts=" in html
    assert "latest.json?ts=" not in html
    assert "Current Market Cards" in html
    assert "Fair value unavailable until sold evidence passes governance." in html
    assert "Active median" in html
    assert "not fair value" in html
