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


def test_seed_market_feed_uses_governed_schema_and_contains_no_card_payloads():
    payload = json.loads(Path("docs/market.json").read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert payload["cards"] == []
    assert payload["generated_at"] is None
    assert "raw" not in json.dumps(payload).casefold()
    assert any("not fair value" in rule for rule in payload["governance"])
    assert any("genuine sold evidence" in rule for rule in payload["governance"])


def test_live_dashboard_consumes_governed_market_feed():
    html = Path("docs/index.html").read_text(encoding="utf-8")

    assert "market.json?ts=" in html
    assert "latest.json?ts=" not in html
    assert "Current Market Cards" in html
    assert "Fair value unavailable until sold evidence passes governance." in html
    assert "Active median" in html
    assert "not fair value" in html
