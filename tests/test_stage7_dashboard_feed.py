from __future__ import annotations

import json
from pathlib import Path

from scripts.stage7_scan import build_parser


def test_stage7_scan_defaults_to_persistent_history_and_market_feed(monkeypatch):
    monkeypatch.setattr("sys.argv", ["stage7_scan.py"])
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
    assert "Research Queue" in html
    assert "Fair value unavailable until sold evidence passes governance." in html
    assert "Family median" in html
    assert "not fair value" in html


def test_dashboard_browses_full_market_catalogue_and_joins_research_safely():
    html = Path("docs/index.html").read_text(encoding="utf-8")

    assert "Full Market Catalogue" in html
    assert "market_cards" in html
    assert "function researchMap()" in html
    assert "function catalogue()" in html
    assert "NOT_RESEARCHED_IN_THIS_SCAN" in html
    assert "Not researched this scan" in html
    assert "no fair value or BUY signal is implied" in html
    assert "full safe active catalogue" in html


def test_research_console_supports_store_sort_and_history_signals():
    html = Path("docs/index.html").read_text(encoding="utf-8")

    assert 'id="storeFilter"' in html
    assert 'id="sortMode"' in html
    assert "Research priority" in html
    assert "History signal" in html
    assert "Price increases" in html
    assert "Stale listings" in html
    assert "history_price_increases" in html
    assert "history_relisted" in html
    assert "history_stale" in html
    assert "Sold evidence is governed separately" in html


def test_dashboard_exposes_strict_cross_store_matches_without_calling_them_fair_value():
    html = Path("docs/index.html").read_text(encoding="utf-8")

    assert "Cross-Store Matches" in html
    assert 'id="familyRows"' in html
    assert 'id="familyCount"' in html
    assert "STRICT_STRUCTURED_IDENTITY" in html
    assert "ACTIVE_ASKS_ONLY_NOT_FAIR_VALUE" in html
    assert "These are active asking-price comparisons only — never fair value." in html
    assert "strictFamilyKey" in html
    assert "cross_store_families" in html


def test_active_store_strip_does_not_misrepresent_ebay_as_acquisition_store():
    html = Path("docs/index.html").read_text(encoding="utf-8")
    store_strip = html.split('<div class="store-strip">', 1)[1].split("</div>", 1)[0]

    assert "Cherry" in store_strip
    assert "Sports Card Store" in store_strip
    assert "Gimko" in store_strip
    assert "Urban Empire" in store_strip
    assert "eBay" not in store_strip
