from card_scanner.exact_discovery import discover_exact_inventory
from card_scanner.models import CardIdentity, Listing
from card_scanner.opportunity_scanner import MultiStoreSource, NamedStoreSource


def listing(source, external_id, *, player, year="2024", card_number="100", parallel="Silver", price=20.0):
    return Listing(
        source=source,
        external_id=external_id,
        url=f"https://{source}.test/{external_id}",
        title=f"{year} Panini Prizm {player} #{card_number} {parallel}",
        sport="NBA",
        price=price,
        identity=CardIdentity(
            sport="NBA",
            player=player,
            year=year,
            brand="Panini",
            set_name="Panini Prizm",
            card_number=card_number,
            parallel=parallel,
        ),
    )


class FakeSource:
    def __init__(self, name, rows_by_query):
        self.name = name
        self.rows_by_query = rows_by_query
        self.calls = []

    def search(self, sport, query="", limit=50):
        self.calls.append((sport, query, limit))
        return list(self.rows_by_query.get(query, []))[:limit]


def test_targeted_discovery_keeps_only_strict_exact_signature_match():
    target = listing("storea", "a1", player="Player One")
    store_b_seed = listing("storeb", "b-seed", player="Someone Else", card_number="9", parallel="Base")
    exact = listing("storeb", "b1", player="Player One")
    different = listing("storeb", "b2", player="Player One", parallel="Red")

    store_a = FakeSource("storea", {"Player One": [target]})
    store_b = FakeSource("storeb", {"Player One": [exact, different]})
    source = MultiStoreSource([
        NamedStoreSource("Store A", store_a),
        NamedStoreSource("Store B", store_b),
    ])

    rows, stats, errors = discover_exact_inventory(
        source,
        [target, store_b_seed],
        max_targets=1,
        results_per_store=20,
    )

    assert errors == []
    assert stats.targets == 1
    assert stats.queries == 1
    assert stats.added_cards == 1
    assert stats.exact_matches_discovered == 1
    assert {row.external_id for row in rows} == {"a1", "b-seed", "b1"}
    assert store_a.calls == []


def test_different_parallel_is_rejected_not_added():
    target = listing("storea", "a1", player="Player One", parallel="Silver")
    store_b_seed = listing("storeb", "b-seed", player="Someone Else", card_number="9", parallel="Base")
    different = listing("storeb", "b2", player="Player One", parallel="Red")

    source = MultiStoreSource([
        NamedStoreSource("Store A", FakeSource("storea", {"Player One": [target]})),
        NamedStoreSource("Store B", FakeSource("storeb", {"Player One": [different]})),
    ])

    rows, stats, _ = discover_exact_inventory(source, [target, store_b_seed], max_targets=1)
    assert stats.exact_matches_discovered == 0
    assert stats.added_cards == 0
    assert {row.external_id for row in rows} == {"a1", "b-seed"}


def test_multiple_exact_targets_for_same_player_share_one_store_query():
    silver = listing("storea", "a1", player="Player One", card_number="100", parallel="Silver")
    red = listing("storea", "a2", player="Player One", card_number="101", parallel="Red")
    store_b_seed = listing("storeb", "b-seed", player="Someone Else", card_number="9", parallel="Base")
    exact_silver = listing("storeb", "b1", player="Player One", card_number="100", parallel="Silver")
    exact_red = listing("storeb", "b2", player="Player One", card_number="101", parallel="Red")
    noise = listing("storeb", "b3", player="Player One", card_number="999", parallel="Gold")

    store_a = FakeSource("storea", {})
    store_b = FakeSource("storeb", {"Player One": [exact_silver, exact_red, noise]})
    source = MultiStoreSource([
        NamedStoreSource("Store A", store_a),
        NamedStoreSource("Store B", store_b),
    ])

    rows, stats, errors = discover_exact_inventory(
        source,
        [silver, red, store_b_seed],
        max_targets=2,
        results_per_store=20,
    )

    assert errors == []
    assert stats.targets == 2
    assert stats.queries == 1
    assert stats.added_cards == 2
    assert stats.exact_matches_discovered == 2
    assert store_b.calls == [("NBA", "Player One", 20)]
    assert {row.external_id for row in rows} == {"a1", "a2", "b-seed", "b1", "b2"}


def test_store_without_successful_broad_sport_is_not_targeted():
    target = listing("storea", "a1", player="Player One")
    unavailable = FakeSource("storec", {"Player One": [listing("storec", "c1", player="Player One")]})
    source = MultiStoreSource([
        NamedStoreSource("Store A", FakeSource("storea", {"Player One": [target]})),
        NamedStoreSource("Store C", unavailable),
    ])

    _, stats, _ = discover_exact_inventory(source, [target], max_targets=1)
    assert stats.queries == 0
    assert unavailable.calls == []
