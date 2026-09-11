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


@dataclass(frozen=True)
class ExactTarget:
    sport: str
    player: str
    year: str
    signature: str
    source_count: int


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
) -> list[ExactTarget]:
    """Choose strict exact-card signatures most likely to create comparisons.

    Discovery used to spend one target on a broad player/year bucket. That wastes
    capacity when a player owns dozens of distinct cards and it can add hundreds
    of unrelated same-player listings. Instead, every target is one strict exact
    signature. Signatures present at only one source rank first because finding
    one copy elsewhere immediately creates a genuine cross-store comparison.
    """
    sources_by_signature: dict[str, set[str]] = defaultdict(set)
    labels: dict[str, tuple[str, str, str]] = {}

    for listing in listings:
        identity = listing.identity
        if identity is None or not identity.player or not identity.year:
            continue
        signature = _eligible_signature(listing)
        if not signature:
            continue
        sport = str(listing.sport).upper().strip()
        player = str(identity.player).strip()
        year = str(identity.year).strip()
        if not sport or not player or not year:
            continue
        sources_by_signature[signature].add(_source(listing.source))
        labels.setdefault(signature, (sport, player, year))

    ranked = sorted(
        sources_by_signature,
        key=lambda sig: (
            0 if len(sources_by_signature[sig]) == 1 else 1,
            len(sources_by_signature[sig]),
            labels[sig][0],
            labels[sig][1].casefold(),
            labels[sig][2],
            sig,
        ),
    )
    return [
        ExactTarget(
            sport=labels[sig][0],
            player=labels[sig][1],
            year=labels[sig][2],
            signature=sig,
            source_count=len(sources_by_signature[sig]),
        )
        for sig in ranked[: max(0, int(max_targets))]
    ]


def discover_exact_inventory(
    source: MultiStoreSource,
    listings: Iterable[Listing],
    *,
    max_targets: int = 16,
    results_per_store: int = 100,
) -> tuple[list[Listing], ExactDiscoveryStats, list[str]]:
    """Search retailers for strict target signatures without weakening identity.

    Targets are exact signatures, but searches are cached by sport/player/year per
    store. That lets one retailer request satisfy many cards for the same player.
    Returned listings are retained only when their strict canonical signature is
    one of the selected target signatures for that player/year. Broad same-player
    inventory is rejected before it can bloat the live feed.
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

    targets_by_query: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    player_labels: dict[tuple[str, str, str], str] = {}
    for target in targets:
        key = (target.sport, _text(target.player), target.year)
        targets_by_query[key].add(target.signature)
        player_labels[key] = target.player

    output = list(base)
    seen = {(_source(row.source), str(row.external_id)) for row in base}
    errors: list[str] = []
    queries = 0
    added = 0
    discovered_signatures: set[str] = set()

    for (sport, player_key, year), target_signatures in targets_by_query.items():
        player = player_labels[(sport, player_key, year)]
        for store_token in sorted(successful_by_sport.get(sport, set())):
            store = stores_by_token.get(store_token)
            if store is None:
                continue
            # Skip the request only if this store already owns every target in
            # this player/year query bucket. Otherwise one search may discover
            # several stranded exact signatures at once.
            if all(store_token in existing_signatures.get(sig, set()) for sig in target_signatures):
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
                sig = _eligible_signature(row)
                if not sig or sig not in target_signatures:
                    continue

                row_source = _source(row.source)
                key = (row_source, str(row.external_id))
                if key in seen:
                    continue
                seen.add(key)
                output.append(row)
                added += 1

                other_sources = existing_signatures.get(sig, set()) - {row_source}
                if other_sources:
                    discovered_signatures.add(sig)
                existing_signatures[sig].add(row_source)

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
