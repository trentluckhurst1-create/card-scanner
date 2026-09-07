from __future__ import annotations

import json

from .comp_key import identity_signature
from .db import add_watch_item, list_watch_items, record_watch_event, remove_watch_item
from .models import Listing, WatchEvent, WatchItem


VALID_WATCH_TYPES = {
    "listing",
    "player",
    "identity_signature",
    "query",
}


def add_watch(
    watch_type: str,
    value: str,
    sport: str | None = None,
    label: str | None = None,
) -> int:
    watch_type = watch_type.lower()

    if watch_type not in VALID_WATCH_TYPES:
        raise ValueError(
            "watch_type must be one of: "
            + ", ".join(sorted(VALID_WATCH_TYPES))
        )

    return add_watch_item(
        WatchItem(
            watch_type=watch_type,
            value=value,
            sport=sport.upper() if sport else None,
            label=label,
        )
    )


def remove_watch(watch_id: int) -> bool:
    return remove_watch_item(watch_id)


def matching_watch_ids(listing: Listing) -> list[int]:
    matches: list[int] = []
    signature = identity_signature(listing.identity) if listing.identity else ""

    for row in list_watch_items():
        sport = row["sport"]
        if sport and sport != listing.sport:
            continue

        watch_type = row["watch_type"]
        value = row["value"]

        if watch_type == "listing" and value == listing.external_id:
            matches.append(int(row["id"]))
        elif watch_type == "player" and listing.identity and listing.identity.player:
            if value.lower() == listing.identity.player.lower():
                matches.append(int(row["id"]))
        elif watch_type == "identity_signature" and value == signature:
            matches.append(int(row["id"]))
        elif watch_type == "query" and value.lower() in listing.title.lower():
            matches.append(int(row["id"]))

    return matches


def record_listing_watch_events(
    listing: Listing,
    event_type: str,
):
    if event_type == "UNCHANGED":
        return

    for watch_id in matching_watch_ids(listing):
        record_watch_event(
            WatchEvent(
                watch_item_id=watch_id,
                event_type=event_type,
                source=listing.source,
                external_id=listing.external_id,
                details={
                    "title": listing.title,
                    "price": listing.price,
                },
            )
        )
