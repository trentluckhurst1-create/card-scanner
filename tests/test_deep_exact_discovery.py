from __future__ import annotations

import importlib.util
from pathlib import Path

from card_scanner.models import CardIdentity, Listing
from card_scanner.opportunity_scanner import MultiStoreSource, NamedStoreSource


def _module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "publish_active_market.py"
    spec = importlib.util.spec_from_file_location("publish_active_market_deep_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _listing(source: str, external_id: str, *, card_number: str, parallel: str) -> Listing:
    return Listing(
        source=source,
        external_id=external_id,
        url=f"https://example.test/{source}/{external_id}",
        title=f"2025 Topps Chrome Test Player {parallel} #{card_number}",
        sport="NFL",
        price=100.0,
        currency="AUD",
        identity=CardIdentity(
            sport="NFL",
            player="Test Player",
            year="2025",
            brand="Topps",
            set_name="Topps Chrome",
            card_number=card_number,
            parallel=parallel,
            rookie=True,
        ),
    )


class _FakeSource:
    def __init__(self, name: str, rows: list[Listing]):
        self.name = name
        self.rows = rows
        self.calls: list[tuple[str, str, int]] = []

    def search(self, sport: str, query: str = "", limit: int = 50) -> list[Listing]:
        self.calls.append((sport, query, limit))
        return list(self.rows)[:limit]


def test_deep_overlap_search_can_recover_strict_exact_match():
    module = _module()
    seed_a = _listing("storea", "a1", card_number="43", parallel="Silver")
    seed_b = _listing("storeb", "b1", card_number="99", parallel="Gold")
    recovered_b = _listing("storeb", "b2", card_number="43", parallel="Silver")

    source_a = _FakeSource("storea", [seed_a])
    source_b = _FakeSource("storeb", [seed_b, recovered_b])
    multi = MultiStoreSource([
        NamedStoreSource(name="Store A", source=source_a),
        NamedStoreSource(name="Store B", source=source_b),
    ])

    expanded, stats, errors = module.expand_shared_player_inventory(
        multi,
        [seed_a, seed_b],
        max_targets=10,
        results_per_store=20,
    )

    assert errors == []
    assert stats == {
        "deep_overlap_targets": 1,
        "deep_overlap_queries": 2,
        "deep_overlap_added_cards": 1,
        "deep_overlap_errors": 0,
    }
    assert source_a.calls == [("NFL", "Test Player", 20)]
    assert source_b.calls == [("NFL", "Test Player", 20)]

    payload = module.build_active_market_payload(expanded, discovery_metrics=stats)
    assert payload["metrics"]["exact_matches"] == 1
    exact = [
        group
        for group in payload["active_price_comparisons"]["groups"]
        if group["comparison_type"] == "EXACT_CARD"
    ]
    assert len(exact) == 1
    assert {row["source"] for row in exact[0]["listings"]} == {"storea", "storeb"}


def test_deep_overlap_search_does_not_expand_single_store_player():
    module = _module()
    seed = _listing("storea", "a1", card_number="43", parallel="Silver")
    source_a = _FakeSource("storea", [seed])
    multi = MultiStoreSource([NamedStoreSource(name="Store A", source=source_a)])

    expanded, stats, errors = module.expand_shared_player_inventory(
        multi,
        [seed],
        max_targets=10,
        results_per_store=20,
    )

    assert expanded == [seed]
    assert errors == []
    assert stats["deep_overlap_targets"] == 0
    assert stats["deep_overlap_queries"] == 0
    assert stats["deep_overlap_added_cards"] == 0
    assert source_a.calls == []
