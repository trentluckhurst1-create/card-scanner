from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .identity_match import canonical_exact_components, exact_components_eligible, exact_signature
from .models import Listing
from .opportunity_scanner import MultiStoreSource, NamedStoreSource


@dataclass(frozen=True)
class ExactDiscoveryStats:
    targets: int = 0
    queries: int = 0
    added_cards: int = 0
    exact_matches_discovered: int = 0
    errors: int = 0


def _text(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _source(value: object) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def _components(listing: Listing) -> dict[str, str] | None:
    if listing.identity is None:
        return None
    return canonical_exact_components(
        sport=listing.sport,
        identity=listing.identity.model_dump(),
    )


def _eligible_signature(listing: Listing) -> str | None:
    components = _components(listing)
    if components is None or not exact_components_eligible(components):
        return None
    return exact_signature(components)


def _dedupe(rows: Iterable[Listing]) -> list[Listing]:
    output: list[Listing] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (_source(row.source), str(row.external_id))
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def _candidate_targets(
    listings: Iterable[Listing],
    *,
    max_targets: int,
) -> list[tuple[str, str, str]]:
    """Choose player/year groups that contain strict-exact-ready inventory.

    One player/year target can represent many exact-ready cards. Searching a
    retailer once for that player lets strict signatures test all of them.
    """
    exact_counts: dict[tuple[str, str, str], int] = defaultdict(int)
    source_counts: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    labels: dict[tuple[str, str, str], str] = {}

    for listing in listings:
        identity = listing.identity
        if identity is None or not identity.player or not identity.year:
            continue
        if _eligible_signature(listing) is None:
            continue
        sport = str(listing.sport).upper()
        player_key = _text(identity.player)
        year = str(identity.year).strip()
        if not sport or not player_key or not year:
            continue
        key = (sport, player_key, year)
        exact_counts[key] += 1
        source_counts[key].add(_source(listing.source))
        labels[key] = str(identity.player).strip()

    ranked = sorted(
        exact_counts,
        key=lambda key: (
            -len(source_counts[key]),
            -exact_counts[key],
            key[0],
            labels[key].casefold(),
            key[2],
        ),
    )
    return [
        (sport, labels[(sport, player_key, year)], year)
        for sport, player_key, year in ranked[: max(0, int(max_targets))]
    ]


def discover_exact_inventory(
    source: MultiStoreSource,
    listings: Iterable[Listing],
    *,
    max_targets: int = 16,
    results_per_store: int = 100,
) -> tuple[list[Listing], ExactDiscoveryStats, list[str]]:
    """Deep-search likely exact identities without weakening exact matching.

    For each selected player/year, query every store that successfully returned
    at least one row for that sport in the broad scan. All discovered listings
    are added to the normal catalogue, but an ``exact_matches_discovered`` count
    increments only when a newly discovered row has the same strict canonical
    exact signature as an existing row from another store.
    """
    base = _dedupe(listings)
    targets = _candidate_targets(base, max_targets=max_targets)

    successful_by_sport: dict[str, set[str]] = defaultdict(set)
    for row in base:
        successful_by_sport[str(row.sport).upper()].add(_source(row.source))

    stores_by_token: dict[str, NamedStoreSource] = {}
    for store in source.stores:
        token = _source(getattr(store.source, "name", None) or store.name)
        stores_by_token[token] = store

    existing_signatures: dict[str, set[str]] = defaultdict(set)
    for row in base:
        sig = _eligible_signature(row)
        if sig:
            existing_signatures[sig].add(_source(row.source))

    output = list(base)
    seen = {(_source(row.source), str(row.external_id)) for row in base}
    errors: list[str] = []
    queries = 0
    added = 0
    discovered_signatures: set[str] = set()

    for sport, player, year in targets:
        player_key = _text(player)
        for store_token in sorted(successful_by_sport.get(sport, set())):
            store = stores_by_token.get(store_token)
            if store is None:
                continue
            queries += 1
            try:
                found = store.source.search(
                    sport=sport,
                    query=player,
                    limit=max(1, int(results_per_store)),
                )
            except Exception as exc:
                errors.append(
                    f"{sport}: {store.name}: exact discovery: {type(exc).__name__}: {exc}"
                )
                continue

            for row in found:
                identity = row.identity
                if identity is None:
                    continue
                if _text(identity.player) != player_key:
                    continue
                if str(identity.year or "").strip() != year:
                    continue

                key = (_source(row.source), str(row.external_id))
                if key in seen:
                    continue
                seen.add(key)
                output.append(row)
                added += 1

                sig = _eligible_signature(row)
                if not sig:
                    continue
                other_sources = existing_signatures.get(sig, set()) - {_source(row.source)}
                if other_sources:
                    discovered_signatures.add(sig)
                existing_signatures[sig].add(_source(row.source))

    return (
        output,
        ExactDiscoveryStats(
            targets=len(targets),
            queries=queries,
            added_cards=added,
            exact_matches_discovered=len(discovered_signatures),
            errors=len(errors),
        ),
        errors,
    )
