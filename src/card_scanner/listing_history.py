from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from sqlite3 import Row

from .comp_key import identity_signature
from .config import settings
from .db import session
from .models import Listing


@dataclass(frozen=True)
class ListingHistoryAssessment:
    source: str
    external_id: str
    history_status: str
    first_seen_at: datetime
    last_seen_at: datetime
    age_days: int
    observation_count: int
    previous_price: float | None
    current_price: float | None
    min_observed_price: float | None
    max_observed_price: float | None
    price_change_count: int
    price_drop_count: int
    price_increase_count: int
    last_price_change_at: datetime | None
    price_change_amount: float | None
    price_change_pct: float | None
    latest_price_drop_pct: float | None
    days_since_price_change: int | None
    is_new: bool
    is_price_drop: bool
    is_price_increase: bool
    is_stale: bool
    is_relisted: bool
    history_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ListingHistoryBatch:
    histories: dict[tuple[str, str], ListingHistoryAssessment]
    observed_count: int
    state_created_count: int
    state_updated_count: int
    unchanged_count: int
    price_drop_count: int
    price_increase_count: int
    relisted_count: int
    stale_count: int
    event_count: int
    errors: tuple[str, ...] = ()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return _utc_now()

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _days_between(
    start: datetime | None,
    end: datetime,
) -> int | None:
    if start is None:
        return None

    return max(0, int((end - start).total_seconds() // 86400))


def _safe_price(value: float | int | None) -> float | None:
    if value is None:
        return None

    try:
        price = float(value)
    except (TypeError, ValueError):
        return None

    if price <= 0:
        return None

    return round(price, 2)


def _safe_shipping(value: float | int | None) -> float | None:
    if value is None:
        return None

    try:
        shipping = float(value)
    except (TypeError, ValueError):
        return None

    if shipping < 0:
        return None

    return round(shipping, 2)


def _landed_aud(
    listing: Listing,
    current_price: float | None,
    shipping: float | None,
) -> float | None:
    if current_price is None:
        return None

    if listing.currency.upper() != "AUD":
        return None

    return round(current_price + float(shipping or 0.0), 2)


def _identity_fingerprint(listing: Listing) -> str | None:
    if listing.identity is None:
        return None

    return identity_signature(listing.identity)


def _identity_json(listing: Listing) -> str | None:
    return listing.identity.model_dump_json() if listing.identity else None


def _price_change(
    old_price: float | None,
    new_price: float | None,
) -> tuple[float | None, float | None]:
    if old_price is None or old_price <= 0 or new_price is None:
        return None, None

    amount = round(new_price - old_price, 2)
    pct = round(amount / old_price * 100.0, 2)

    return amount, pct


def _event_type(
    row: Row | None,
    listing: Listing,
    current_price: float | None,
    identity_fingerprint_value: str | None,
) -> tuple[str, list[str]]:
    notes: list[str] = []

    if row is None:
        if current_price is None:
            notes.append("price unavailable; no price comparison possible")
        return "NEW_LISTING", notes

    if int(row["active"] or 0) == 0:
        return "RELISTED", notes

    if current_price is None:
        notes.append("price unavailable; no price comparison possible")
        return "PRICE_UNAVAILABLE", notes

    previous = _safe_price(row["current_price"])

    if str(row["currency"]).upper() != listing.currency.upper():
        notes.append("currency changed; price movement not compared")
        return "CURRENCY_CHANGED", notes

    if previous is not None and current_price < previous:
        return "PRICE_DROP", notes

    if previous is not None and current_price > previous:
        return "PRICE_INCREASE", notes

    if previous is None:
        notes.append("previous price unavailable; price movement not compared")
        return "UNCHANGED", notes

    if (
        listing.title != row["title"]
        or listing.url != row["url"]
        or _identity_fingerprint(listing) != row["identity_fingerprint"]
    ):
        return "UPDATED", notes

    return "UNCHANGED", notes


def _row_to_assessment(
    row: Row,
    *,
    observed_at: datetime,
    stale_after_days: int,
    notes: tuple[str, ...] = (),
) -> ListingHistoryAssessment:
    first_seen = _parse_dt(row["first_seen_at"]) or observed_at
    last_seen = _parse_dt(row["last_seen_at"]) or observed_at
    last_change = _parse_dt(row["last_price_change_at"])
    age_days = _days_between(first_seen, observed_at) or 0
    days_since_change = _days_between(last_change, observed_at)
    status = str(row["history_status"])
    latest_pct = row["latest_price_change_pct"]
    latest_drop_pct = (
        abs(float(latest_pct))
        if latest_pct is not None and float(latest_pct) < 0
        else None
    )

    return ListingHistoryAssessment(
        source=row["source"],
        external_id=row["external_id"],
        history_status=status,
        first_seen_at=first_seen,
        last_seen_at=last_seen,
        age_days=age_days,
        observation_count=int(row["observation_count"] or 0),
        previous_price=(
            float(row["previous_price"])
            if row["previous_price"] is not None
            else None
        ),
        current_price=(
            float(row["current_price"])
            if row["current_price"] is not None
            else None
        ),
        min_observed_price=(
            float(row["min_observed_price"])
            if row["min_observed_price"] is not None
            else None
        ),
        max_observed_price=(
            float(row["max_observed_price"])
            if row["max_observed_price"] is not None
            else None
        ),
        price_change_count=int(row["price_change_count"] or 0),
        price_drop_count=int(row["price_drop_count"] or 0),
        price_increase_count=int(row["price_increase_count"] or 0),
        last_price_change_at=last_change,
        price_change_amount=(
            float(row["latest_price_change_amount"])
            if row["latest_price_change_amount"] is not None
            else None
        ),
        price_change_pct=(
            float(row["latest_price_change_pct"])
            if row["latest_price_change_pct"] is not None
            else None
        ),
        latest_price_drop_pct=latest_drop_pct,
        days_since_price_change=days_since_change,
        is_new=status == "NEW_LISTING",
        is_price_drop=status == "PRICE_DROP",
        is_price_increase=status == "PRICE_INCREASE",
        is_stale=age_days >= stale_after_days,
        is_relisted=status == "RELISTED",
        history_notes=notes,
    )


def get_listing_history(
    source: str,
    external_id: str,
    *,
    as_of: datetime | None = None,
    stale_after_days: int | None = None,
) -> ListingHistoryAssessment | None:
    observed_at = _as_utc(as_of)
    stale_days = int(
        settings.listing_stale_days
        if stale_after_days is None
        else stale_after_days
    )

    with session() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM store_listing_states
            WHERE source=? AND external_id=?
            """,
            (source, external_id),
        ).fetchone()

    if row is None:
        return None

    return _row_to_assessment(
        row,
        observed_at=observed_at,
        stale_after_days=stale_days,
    )


def record_store_listing_observation(
    listing: Listing,
    *,
    observed_at: datetime | None = None,
    scan_run_id: int | None = None,
    stale_after_days: int | None = None,
) -> ListingHistoryAssessment:
    observed = _as_utc(observed_at)
    observed_text = observed.isoformat()
    stale_days = int(
        settings.listing_stale_days
        if stale_after_days is None
        else stale_after_days
    )
    current_price = _safe_price(listing.price)
    shipping = _safe_shipping(listing.shipping)
    landed = _landed_aud(listing, current_price, shipping)
    identity_json = _identity_json(listing)
    fingerprint = _identity_fingerprint(listing)

    with session() as conn:
        existing = conn.execute(
            """
            SELECT *
            FROM store_listing_states
            WHERE source=? AND external_id=?
            """,
            (listing.source, listing.external_id),
        ).fetchone()

        if existing is not None and existing["last_seen_at"] == observed_text:
            return _row_to_assessment(
                existing,
                observed_at=observed,
                stale_after_days=stale_days,
                notes=("duplicate observation timestamp ignored",),
            )

        status, notes = _event_type(
            existing,
            listing,
            current_price,
            fingerprint,
        )

        first_seen = (
            observed_text
            if existing is None
            else existing["first_seen_at"]
        )
        previous_price = (
            _safe_price(existing["current_price"])
            if existing is not None
            else None
        )
        amount, pct = _price_change(previous_price, current_price)
        is_price_change = status in {"PRICE_DROP", "PRICE_INCREASE"}
        price_change_count = (
            (int(existing["price_change_count"] or 0) if existing else 0)
            + (1 if is_price_change else 0)
        )
        price_drop_count = (
            (int(existing["price_drop_count"] or 0) if existing else 0)
            + (1 if status == "PRICE_DROP" else 0)
        )
        price_increase_count = (
            (int(existing["price_increase_count"] or 0) if existing else 0)
            + (1 if status == "PRICE_INCREASE" else 0)
        )

        if existing is None:
            min_price = current_price
            max_price = current_price
        elif (
            str(existing["currency"]).upper()
            != listing.currency.upper()
        ):
            min_price = current_price
            max_price = current_price
        else:
            seen_prices = [
                value
                for value in [
                    _safe_price(existing["min_observed_price"]),
                    _safe_price(existing["max_observed_price"]),
                    current_price,
                ]
                if value is not None
            ]
            min_price = min(seen_prices) if seen_prices else None
            max_price = max(seen_prices) if seen_prices else None

        last_price_change_at = (
            observed_text
            if is_price_change
            else (
                existing["last_price_change_at"]
                if existing is not None
                else None
            )
        )
        latest_amount = (
            amount
            if is_price_change
            else (
                existing["latest_price_change_amount"]
                if existing is not None
                else None
            )
        )
        latest_pct = (
            pct
            if is_price_change
            else (
                existing["latest_price_change_pct"]
                if existing is not None
                else None
            )
        )
        observation_count = (
            (int(existing["observation_count"] or 0) if existing else 0)
            + 1
        )

        conn.execute(
            """
            INSERT INTO store_listing_states
            (source, external_id, sport, url, title, price, currency,
             shipping, landed_aud, first_seen_at, last_seen_at,
             previous_price, current_price, min_observed_price,
             max_observed_price, observation_count, price_change_count,
             price_drop_count, price_increase_count, last_price_change_at,
             latest_price_change_amount, latest_price_change_pct,
             history_status, identity_json, identity_fingerprint, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(source, external_id) DO UPDATE SET
                sport=excluded.sport,
                url=excluded.url,
                title=excluded.title,
                price=excluded.price,
                currency=excluded.currency,
                shipping=excluded.shipping,
                landed_aud=excluded.landed_aud,
                last_seen_at=excluded.last_seen_at,
                previous_price=excluded.previous_price,
                current_price=excluded.current_price,
                min_observed_price=excluded.min_observed_price,
                max_observed_price=excluded.max_observed_price,
                observation_count=excluded.observation_count,
                price_change_count=excluded.price_change_count,
                price_drop_count=excluded.price_drop_count,
                price_increase_count=excluded.price_increase_count,
                last_price_change_at=excluded.last_price_change_at,
                latest_price_change_amount=excluded.latest_price_change_amount,
                latest_price_change_pct=excluded.latest_price_change_pct,
                history_status=excluded.history_status,
                identity_json=excluded.identity_json,
                identity_fingerprint=excluded.identity_fingerprint,
                active=1
            """,
            (
                listing.source,
                listing.external_id,
                listing.sport.upper(),
                listing.url,
                listing.title,
                current_price,
                listing.currency.upper(),
                shipping,
                landed,
                first_seen,
                observed_text,
                previous_price,
                current_price,
                min_price,
                max_price,
                observation_count,
                price_change_count,
                price_drop_count,
                price_increase_count,
                last_price_change_at,
                latest_amount,
                latest_pct,
                status,
                identity_json,
                fingerprint,
            ),
        )

        if status != "UNCHANGED":
            conn.execute(
                """
                INSERT OR IGNORE INTO store_listing_price_events
                (source, external_id, observed_at, event_type,
                 previous_price, current_price, price_change_amount,
                 price_change_pct, currency, scan_run_id, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    listing.source,
                    listing.external_id,
                    observed_text,
                    status,
                    previous_price,
                    current_price,
                    amount if is_price_change else None,
                    pct if is_price_change else None,
                    listing.currency.upper(),
                    scan_run_id,
                    json.dumps(
                        {
                            "sport": listing.sport.upper(),
                            "title": listing.title,
                            "url": listing.url,
                            "landed_aud": landed,
                            "notes": notes,
                        }
                    ),
                ),
            )

        row = conn.execute(
            """
            SELECT *
            FROM store_listing_states
            WHERE source=? AND external_id=?
            """,
            (listing.source, listing.external_id),
        ).fetchone()

        return _row_to_assessment(
            row,
            observed_at=observed,
            stale_after_days=stale_days,
            notes=tuple(notes),
        )


def record_store_listing_observations(
    listings: list[Listing],
    *,
    observed_at: datetime | None = None,
    scan_run_id: int | None = None,
    stale_after_days: int | None = None,
) -> ListingHistoryBatch:
    observed = _as_utc(observed_at)
    histories: dict[tuple[str, str], ListingHistoryAssessment] = {}
    errors: list[str] = []
    created = 0
    updated = 0
    unchanged = 0
    drops = 0
    increases = 0
    relisted = 0
    stale = 0
    events = 0

    for listing in listings:
        try:
            history = record_store_listing_observation(
                listing,
                observed_at=observed,
                scan_run_id=scan_run_id,
                stale_after_days=stale_after_days,
            )
        except Exception as exc:
            errors.append(
                f"{listing.source}:{listing.external_id}: "
                f"{type(exc).__name__}: {exc}"
            )
            continue

        histories[(listing.source.casefold(), listing.external_id)] = history

        if history.history_status == "NEW_LISTING":
            created += 1
            events += 1
        else:
            updated += 1
            if history.history_status != "UNCHANGED":
                events += 1

        if history.history_status == "UNCHANGED":
            unchanged += 1
        elif history.history_status == "PRICE_DROP":
            drops += 1
        elif history.history_status == "PRICE_INCREASE":
            increases += 1
        elif history.history_status == "RELISTED":
            relisted += 1

        if history.is_stale:
            stale += 1

    return ListingHistoryBatch(
        histories=histories,
        observed_count=len(histories),
        state_created_count=created,
        state_updated_count=updated,
        unchanged_count=unchanged,
        price_drop_count=drops,
        price_increase_count=increases,
        relisted_count=relisted,
        stale_count=stale,
        event_count=events,
        errors=tuple(errors),
    )
