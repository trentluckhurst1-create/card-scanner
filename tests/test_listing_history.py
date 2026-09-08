from __future__ import annotations

import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import card_scanner.db as db
from card_scanner.identity import parse_identity
from card_scanner.listing_history import (
    get_listing_history,
    record_store_listing_observation,
    record_store_listing_observations,
)
from card_scanner.models import Listing
from card_scanner.opportunity_scanner import scan_store_opportunities


def dt(day: int) -> datetime:
    return datetime(2026, 9, day, 12, 0, tzinfo=timezone.utc)


def make_listing(
    *,
    source: str = "cherry",
    external_id: str = "card-1",
    price: float = 100.0,
    currency: str = "AUD",
    title: str = (
        "2025 Bowman Draft KYSON WITHERSPOON "
        "Chrome Prospect 1st Auto Gold Wave 38/50"
    ),
) -> Listing:
    return Listing(
        source=source,
        external_id=external_id,
        url=f"https://example.invalid/{source}/{external_id}",
        title=title,
        sport="MLB",
        price=price,
        currency=currency,
        shipping=5.0,
        identity=parse_identity(title, "MLB"),
    )


class TempDb:
    def __enter__(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_settings = db.settings
        db.settings = SimpleNamespace(
            db_path=str(Path(self.temp_dir.name) / "scanner.sqlite3")
        )
        db.init_db()
        return db.settings.db_path

    def __exit__(self, exc_type, exc, tb):
        db.settings = self.original_settings
        self.temp_dir.cleanup()


def test_first_observation_is_new_listing():
    with TempDb():
        history = record_store_listing_observation(
            make_listing(),
            observed_at=dt(1),
            stale_after_days=45,
        )

        assert history.history_status == "NEW_LISTING"
        assert history.is_new
        assert history.first_seen_at == dt(1)
        assert history.last_seen_at == dt(1)
        assert history.observation_count == 1
        assert history.current_price == 100.0
        assert history.previous_price is None


def test_same_listing_same_price_is_unchanged_and_preserves_first_seen():
    with TempDb():
        record_store_listing_observation(make_listing(), observed_at=dt(1))
        history = record_store_listing_observation(
            make_listing(),
            observed_at=dt(2),
        )

        assert history.history_status == "UNCHANGED"
        assert history.first_seen_at == dt(1)
        assert history.last_seen_at == dt(2)
        assert history.observation_count == 2
        assert history.price_change_count == 0


def test_price_decrease_records_price_drop():
    with TempDb():
        record_store_listing_observation(make_listing(price=100), observed_at=dt(1))
        history = record_store_listing_observation(
            make_listing(price=80),
            observed_at=dt(2),
        )

        assert history.history_status == "PRICE_DROP"
        assert history.is_price_drop
        assert history.previous_price == 100.0
        assert history.current_price == 80.0
        assert history.price_change_amount == -20.0
        assert history.price_change_pct == -20.0
        assert history.price_drop_count == 1
        assert history.latest_price_drop_pct == 20.0


def test_price_increase_records_price_increase():
    with TempDb():
        record_store_listing_observation(make_listing(price=100), observed_at=dt(1))
        history = record_store_listing_observation(
            make_listing(price=125),
            observed_at=dt(2),
        )

        assert history.history_status == "PRICE_INCREASE"
        assert history.is_price_increase
        assert history.price_change_amount == 25.0
        assert history.price_change_pct == 25.0
        assert history.price_increase_count == 1


def test_multiple_observations_calculate_counts_and_min_max():
    with TempDb():
        record_store_listing_observation(make_listing(price=100), observed_at=dt(1))
        record_store_listing_observation(make_listing(price=80), observed_at=dt(2))
        history = record_store_listing_observation(
            make_listing(price=95),
            observed_at=dt(3),
        )

        assert history.observation_count == 3
        assert history.price_change_count == 2
        assert history.price_drop_count == 1
        assert history.price_increase_count == 1
        assert history.min_observed_price == 80.0
        assert history.max_observed_price == 100.0
        assert history.days_since_price_change == 0


def test_stale_threshold_is_configurable():
    with TempDb():
        record_store_listing_observation(make_listing(), observed_at=dt(1))
        history = record_store_listing_observation(
            make_listing(),
            observed_at=dt(10),
            stale_after_days=7,
        )

        assert history.age_days == 9
        assert history.is_stale


def test_missing_price_is_handled_without_price_change():
    with TempDb():
        record_store_listing_observation(make_listing(price=100), observed_at=dt(1))
        history = record_store_listing_observation(
            make_listing(price=0),
            observed_at=dt(2),
        )

        assert history.history_status == "PRICE_UNAVAILABLE"
        assert history.current_price is None
        assert history.price_change_amount is None
        assert history.price_change_pct is None
        assert "price unavailable" in " ".join(history.history_notes)


def test_currency_change_does_not_compare_prices():
    with TempDb():
        record_store_listing_observation(make_listing(price=100), observed_at=dt(1))
        history = record_store_listing_observation(
            make_listing(price=70, currency="USD"),
            observed_at=dt(2),
        )

        assert history.history_status == "CURRENCY_CHANGED"
        assert history.price_change_amount is None
        assert history.price_change_pct is None
        assert history.min_observed_price == 70.0
        assert history.max_observed_price == 70.0


def test_source_and_external_id_are_unique_key():
    with TempDb():
        first = record_store_listing_observation(
            make_listing(source="cherry", external_id="same"),
            observed_at=dt(1),
        )
        second = record_store_listing_observation(
            make_listing(source="gimko", external_id="same"),
            observed_at=dt(1),
        )

        assert first.history_status == "NEW_LISTING"
        assert second.history_status == "NEW_LISTING"

        with closing(sqlite3.connect(db.settings.db_path)) as conn:
            assert conn.execute(
                "SELECT COUNT(*) FROM store_listing_states"
            ).fetchone()[0] == 2


def test_duplicate_observation_timestamp_is_idempotent():
    with TempDb():
        record_store_listing_observation(make_listing(), observed_at=dt(1))
        duplicate = record_store_listing_observation(
            make_listing(price=90),
            observed_at=dt(1),
        )

        assert duplicate.observation_count == 1
        assert duplicate.current_price == 100.0
        assert "duplicate observation timestamp ignored" in duplicate.history_notes

        with closing(sqlite3.connect(db.settings.db_path)) as conn:
            assert conn.execute(
                "SELECT COUNT(*) FROM store_listing_price_events"
            ).fetchone()[0] == 1


def test_relisted_only_when_state_was_explicitly_inactive():
    with TempDb():
        record_store_listing_observation(make_listing(), observed_at=dt(1))
        with closing(sqlite3.connect(db.settings.db_path)) as conn:
            conn.execute(
                """
                UPDATE store_listing_states
                SET active=0
                WHERE source='cherry' AND external_id='card-1'
                """
            )
            conn.commit()

        history = record_store_listing_observation(
            make_listing(),
            observed_at=dt(2),
        )

        assert history.history_status == "RELISTED"
        assert history.is_relisted


def test_get_listing_history_reads_existing_state():
    with TempDb():
        record_store_listing_observation(make_listing(), observed_at=dt(1))
        history = get_listing_history(
            "cherry",
            "card-1",
            as_of=dt(3),
        )

        assert history is not None
        assert history.age_days == 2
        assert history.observation_count == 1


def test_batch_summary_counts_history_events():
    with TempDb():
        record_store_listing_observations(
            [
                make_listing(external_id="one", price=100),
                make_listing(external_id="two", price=100),
            ],
            observed_at=dt(1),
        )
        batch = record_store_listing_observations(
            [
                make_listing(external_id="one", price=80),
                make_listing(external_id="two", price=100),
            ],
            observed_at=dt(2),
        )

        assert batch.observed_count == 2
        assert batch.state_created_count == 0
        assert batch.state_updated_count == 2
        assert batch.price_drop_count == 1
        assert batch.unchanged_count == 1
        assert batch.event_count == 1


def test_partial_empty_scan_does_not_mark_prior_listing_inactive():
    class EmptyStore:
        def search(self, sport, query="", limit=50):
            return []

    with TempDb():
        record_store_listing_observation(make_listing(), observed_at=dt(1))

        scan_store_opportunities(
            store_source=EmptyStore(),
            sold_provider=None,
            sport="MLB",
            listings_per_sport=5,
            max_candidates_per_sport=0,
            max_sold_queries=0,
            record_history=True,
            history_observed_at=dt(2),
        )

        with closing(sqlite3.connect(db.settings.db_path)) as conn:
            assert conn.execute(
                """
                SELECT active
                FROM store_listing_states
                WHERE source='cherry' AND external_id='card-1'
                """
            ).fetchone()[0] == 1
