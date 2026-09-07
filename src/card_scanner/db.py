from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .config import settings
from .models import (
    ActiveMarketMetrics,
    CardIdentity,
    Listing,
    MarketListing,
    MarketMatch,
    SoldComp,
    SoldCompMatch,
    SoldValuation,
    Opportunity,
    WatchItem,
    WatchEvent,
    Valuation,
)

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    sport TEXT NOT NULL,
    price REAL NOT NULL,
    currency TEXT NOT NULL,
    shipping REAL NOT NULL DEFAULT 0,
    image_url TEXT,
    seller TEXT,
    condition TEXT,
    discovered_at TEXT NOT NULL,
    identity_json TEXT,
    first_seen TEXT,
    last_seen TEXT,
    last_price REAL,
    current_price REAL,
    active INTEGER NOT NULL DEFAULT 1,
    missed_scan_count INTEGER NOT NULL DEFAULT 0,
    last_scan_run_id INTEGER,
    last_change_type TEXT,
    UNIQUE(source, external_id)
);

CREATE TABLE IF NOT EXISTS listing_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    price REAL NOT NULL,
    shipping REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL,
    scan_run_id INTEGER,
    event_type TEXT
);

CREATE TABLE IF NOT EXISTS valuations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    landed_cost_aud REAL NOT NULL,
    fair_value_aud REAL,
    quick_sale_value_aud REAL,
    comp_count INTEGER NOT NULL,
    comp_confidence REAL NOT NULL,
    liquidity REAL NOT NULL,
    identity_confidence REAL NOT NULL,
    risk_penalty REAL NOT NULL,
    opportunity_score REAL NOT NULL,
    edge_pct REAL
);

CREATE INDEX IF NOT EXISTS idx_listings_sport ON listings(sport);
CREATE INDEX IF NOT EXISTS idx_valuations_score ON valuations(opportunity_score DESC);

CREATE TABLE IF NOT EXISTS scan_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    sport TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'RUNNING',
    notes TEXT
);

CREATE TABLE IF NOT EXISTS cherry_scan_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_run_id INTEGER NOT NULL,
    sport TEXT NOT NULL,
    fetched INTEGER NOT NULL,
    new INTEGER NOT NULL,
    updated INTEGER NOT NULL,
    unchanged INTEGER NOT NULL,
    price_drops INTEGER NOT NULL,
    price_rises INTEGER NOT NULL,
    missing INTEGER NOT NULL,
    inactive INTEGER NOT NULL,
    errors INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(scan_run_id, sport)
);

CREATE TABLE IF NOT EXISTS listing_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_run_id INTEGER,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    old_price REAL,
    new_price REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    details_json TEXT
);

CREATE TABLE IF NOT EXISTS market_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    price REAL NOT NULL,
    currency TEXT NOT NULL,
    shipping REAL,
    seller TEXT,
    condition TEXT,
    buying_option TEXT,
    image_url TEXT,
    marketplace TEXT NOT NULL,
    discovered_at TEXT NOT NULL,
    first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    identity_json TEXT,
    risk_flags_json TEXT,
    landed_price_aud REAL,
    fx_status TEXT NOT NULL,
    UNIQUE(source, external_id)
);

CREATE TABLE IF NOT EXISTS market_listing_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    price REAL NOT NULL,
    shipping REAL,
    currency TEXT NOT NULL,
    landed_price_aud REAL,
    fx_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_run_id INTEGER,
    source_listing_external_id TEXT NOT NULL,
    market_source TEXT NOT NULL,
    market_external_id TEXT NOT NULL,
    match_level TEXT NOT NULL,
    match_score REAL NOT NULL,
    match_reasons_json TEXT NOT NULL,
    rejection_reasons_json TEXT NOT NULL,
    risk_flags_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(scan_run_id, source_listing_external_id, market_source, market_external_id)
);

CREATE TABLE IF NOT EXISTS market_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_run_id INTEGER,
    source_listing_external_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    active_match_count INTEGER NOT NULL,
    active_exact_count INTEGER NOT NULL,
    active_strong_count INTEGER NOT NULL,
    active_lowest_aud REAL,
    active_median_aud REAL,
    active_trimmed_median_aud REAL,
    active_mean_aud REAL,
    active_max_aud REAL,
    active_market_spread REAL,
    cherry_vs_active_lowest_pct REAL,
    cherry_vs_active_median_pct REAL,
    market_match_confidence REAL NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sold_comps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    sale_id TEXT NOT NULL,
    sold_date TEXT NOT NULL,
    title TEXT NOT NULL,
    sold_price REAL NOT NULL,
    currency TEXT NOT NULL,
    shipping REAL,
    sold_price_aud REAL,
    sale_type TEXT,
    url TEXT,
    notes TEXT,
    identity_json TEXT,
    imported_at TEXT NOT NULL,
    UNIQUE(source, sale_id)
);

CREATE TABLE IF NOT EXISTS sold_comp_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_listing_external_id TEXT NOT NULL,
    sold_source TEXT NOT NULL,
    sale_id TEXT NOT NULL,
    match_level TEXT NOT NULL,
    match_score REAL NOT NULL,
    match_reasons_json TEXT NOT NULL,
    rejection_reasons_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_listing_external_id, sold_source, sale_id)
);

CREATE TABLE IF NOT EXISTS sold_valuations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_listing_external_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sold_comp_count INTEGER NOT NULL,
    exact_comp_count INTEGER NOT NULL,
    strong_comp_count INTEGER NOT NULL,
    related_comp_count INTEGER NOT NULL,
    latest_sale_aud REAL,
    median_sale_aud REAL,
    weighted_median_aud REAL,
    trimmed_mean_aud REAL,
    median_30_day_aud REAL,
    median_90_day_aud REAL,
    median_180_day_aud REAL,
    fair_value_aud REAL,
    quick_sale_value_aud REAL,
    liquidity_score REAL NOT NULL,
    comp_confidence REAL NOT NULL,
    market_direction TEXT NOT NULL,
    market_direction_reason TEXT NOT NULL,
    status TEXT NOT NULL,
    explanation_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_listing_external_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    landed_cost_aud REAL,
    fair_value_aud REAL,
    quick_sale_value_aud REAL,
    edge_pct REAL,
    opportunity_score REAL NOT NULL,
    identity_confidence REAL NOT NULL,
    comp_confidence REAL NOT NULL,
    liquidity_score REAL NOT NULL,
    risk_score REAL NOT NULL,
    market_direction TEXT NOT NULL,
    status TEXT NOT NULL,
    reasons_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watch_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watch_type TEXT NOT NULL,
    value TEXT NOT NULL,
    sport TEXT,
    label TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(watch_type, value, sport)
);

CREATE TABLE IF NOT EXISTS watch_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watch_item_id INTEGER,
    event_type TEXT NOT NULL,
    source TEXT,
    external_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    details_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_market_matches_listing ON market_matches(source_listing_external_id);
CREATE INDEX IF NOT EXISTS idx_market_metrics_listing ON market_metrics(source_listing_external_id);
CREATE INDEX IF NOT EXISTS idx_sold_comp_matches_listing ON sold_comp_matches(source_listing_external_id);
CREATE INDEX IF NOT EXISTS idx_listing_events_listing ON listing_events(source, external_id);
CREATE INDEX IF NOT EXISTS idx_sold_valuations_listing ON sold_valuations(source_listing_external_id);
CREATE INDEX IF NOT EXISTS idx_opportunities_status ON opportunities(status, opportunity_score DESC);
CREATE INDEX IF NOT EXISTS idx_watch_events_item ON watch_events(watch_item_id);
"""

def connect():
    path = Path(settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})")
    }


def _ensure_column(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
):
    if column not in _columns(conn, table):
        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def _run_migrations(conn: sqlite3.Connection):
    listing_columns = {
        "first_seen": "TEXT",
        "last_seen": "TEXT",
        "last_price": "REAL",
        "current_price": "REAL",
        "active": "INTEGER NOT NULL DEFAULT 1",
        "missed_scan_count": "INTEGER NOT NULL DEFAULT 0",
        "last_scan_run_id": "INTEGER",
        "last_change_type": "TEXT",
    }
    for column, definition in listing_columns.items():
        _ensure_column(conn, "listings", column, definition)

    snapshot_columns = {
        "scan_run_id": "INTEGER",
        "event_type": "TEXT",
    }
    for column, definition in snapshot_columns.items():
        _ensure_column(conn, "listing_snapshots", column, definition)

    conn.execute(
        """
        UPDATE listings
        SET first_seen=COALESCE(first_seen, discovered_at, CURRENT_TIMESTAMP),
            last_seen=COALESCE(last_seen, discovered_at, CURRENT_TIMESTAMP),
            last_price=COALESCE(last_price, price),
            current_price=COALESCE(current_price, price),
            active=COALESCE(active, 1),
            missed_scan_count=COALESCE(missed_scan_count, 0)
        """
    )


def init_db():
    with session() as conn:
        conn.executescript(SCHEMA)
        _run_migrations(conn)


def start_scan_run(source: str, sport: str) -> int:
    with session() as conn:
        cursor = conn.execute(
            """
            INSERT INTO scan_runs(source, sport)
            VALUES (?, ?)
            """,
            (source, sport.upper()),
        )

        return int(cursor.lastrowid)


def finish_scan_run(
    scan_run_id: int,
    status: str,
    notes: str | None = None,
):
    with session() as conn:
        conn.execute(
            """
            UPDATE scan_runs
            SET finished_at=CURRENT_TIMESTAMP,
                status=?,
                notes=?
            WHERE id=?
            """,
            (status, notes, scan_run_id),
        )


def recent_successful_scan(
    source: str,
    sport: str,
    cache_minutes: float,
) -> bool:
    with session() as conn:
        row = conn.execute(
            """
            SELECT id
            FROM scan_runs
            WHERE source=?
              AND sport=?
              AND status='PASS'
              AND started_at >= datetime('now', ?)
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                source,
                sport.upper(),
                f"-{float(cache_minutes)} minutes",
            ),
        ).fetchone()

    return row is not None


def save_cherry_scan_summary(
    scan_run_id: int,
    sport: str,
    summary: dict[str, int],
):
    with session() as conn:
        conn.execute(
            """
            INSERT INTO cherry_scan_summaries
            (scan_run_id, sport, fetched, new, updated, unchanged,
             price_drops, price_rises, missing, inactive, errors)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(scan_run_id, sport) DO UPDATE SET
                fetched=excluded.fetched,
                new=excluded.new,
                updated=excluded.updated,
                unchanged=excluded.unchanged,
                price_drops=excluded.price_drops,
                price_rises=excluded.price_rises,
                missing=excluded.missing,
                inactive=excluded.inactive,
                errors=excluded.errors
            """,
            (
                scan_run_id,
                sport.upper(),
                summary.get("fetched", 0),
                summary.get("new", 0),
                summary.get("updated", 0),
                summary.get("unchanged", 0),
                summary.get("price_drops", 0),
                summary.get("price_rises", 0),
                summary.get("missing", 0),
                summary.get("inactive", 0),
                summary.get("errors", 0),
            ),
        )


def record_listing_event(
    source: str,
    external_id: str,
    event_type: str,
    scan_run_id: int | None = None,
    old_price: float | None = None,
    new_price: float | None = None,
    details: dict | None = None,
):
    with session() as conn:
        conn.execute(
            """
            INSERT INTO listing_events
            (scan_run_id, source, external_id, event_type, old_price, new_price, details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scan_run_id,
                source,
                external_id,
                event_type,
                old_price,
                new_price,
                json.dumps(details or {}),
            ),
        )


def upsert_listing(listing: Listing):
    with session() as conn:
        conn.execute(
            """
            INSERT INTO listings
            (source, external_id, url, title, sport, price, currency, shipping,
             image_url, seller, condition, discovered_at, identity_json,
             first_seen, last_seen, last_price, current_price, active,
             missed_scan_count, last_change_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, external_id) DO UPDATE SET
                url=excluded.url,
                title=excluded.title,
                sport=excluded.sport,
                price=excluded.price,
                currency=excluded.currency,
                shipping=excluded.shipping,
                image_url=excluded.image_url,
                seller=excluded.seller,
                condition=excluded.condition,
                identity_json=excluded.identity_json,
                last_seen=CURRENT_TIMESTAMP,
                current_price=excluded.current_price,
                active=1,
                missed_scan_count=0
            """,
            (
                listing.source, listing.external_id, listing.url, listing.title,
                listing.sport, listing.price, listing.currency, listing.shipping,
                listing.image_url, listing.seller, listing.condition,
                listing.discovered_at.isoformat(),
                listing.identity.model_dump_json() if listing.identity else None,
                listing.discovered_at.isoformat(),
                listing.discovered_at.isoformat(),
                listing.price,
                listing.price,
                1,
                0,
                "UPSERT",
            ),
        )
        conn.execute(
            """
            INSERT INTO listing_snapshots
            (source, external_id, price, shipping, currency, event_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                listing.source,
                listing.external_id,
                listing.price,
                listing.shipping,
                listing.currency,
                "UPSERT",
            ),
        )


def upsert_inventory_listing(
    listing: Listing,
    scan_run_id: int,
) -> str:
    with session() as conn:
        existing = conn.execute(
            """
            SELECT *
            FROM listings
            WHERE source=? AND external_id=?
            """,
            (listing.source, listing.external_id),
        ).fetchone()

        identity_json = listing.identity.model_dump_json() if listing.identity else None
        old_price = (
            float(existing["current_price"] if existing["current_price"] is not None else existing["price"])
            if existing
            else None
        )

        if existing is None:
            event_type = "NEW_LISTING"
            conn.execute(
                """
                INSERT INTO listings
                (source, external_id, url, title, sport, price, currency, shipping,
                 image_url, seller, condition, discovered_at, identity_json,
                 first_seen, last_seen, last_price, current_price, active,
                 missed_scan_count, last_scan_run_id, last_change_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP,
                        ?, ?, 1, 0, ?, ?)
                """,
                (
                    listing.source,
                    listing.external_id,
                    listing.url,
                    listing.title,
                    listing.sport,
                    listing.price,
                    listing.currency,
                    listing.shipping,
                    listing.image_url,
                    listing.seller,
                    listing.condition,
                    listing.discovered_at.isoformat(),
                    identity_json,
                    listing.discovered_at.isoformat(),
                    listing.price,
                    listing.price,
                    scan_run_id,
                    event_type,
                ),
            )
        else:
            if int(existing["active"] or 0) == 0:
                event_type = "RELISTED"
            elif old_price is not None and listing.price < old_price:
                event_type = "PRICE_DROP"
            elif old_price is not None and listing.price > old_price:
                event_type = "PRICE_RISE"
            elif (
                listing.title != existing["title"]
                or listing.url != existing["url"]
                or listing.image_url != existing["image_url"]
                or listing.condition != existing["condition"]
            ):
                event_type = "UPDATED"
            else:
                event_type = "UNCHANGED"

            conn.execute(
                """
                UPDATE listings
                SET url=?,
                    title=?,
                    sport=?,
                    price=?,
                    currency=?,
                    shipping=?,
                    image_url=?,
                    seller=?,
                    condition=?,
                    identity_json=?,
                    last_seen=CURRENT_TIMESTAMP,
                    last_price=?,
                    current_price=?,
                    active=1,
                    missed_scan_count=0,
                    last_scan_run_id=?,
                    last_change_type=?
                WHERE source=? AND external_id=?
                """,
                (
                    listing.url,
                    listing.title,
                    listing.sport,
                    listing.price,
                    listing.currency,
                    listing.shipping,
                    listing.image_url,
                    listing.seller,
                    listing.condition,
                    identity_json,
                    old_price,
                    listing.price,
                    scan_run_id,
                    event_type,
                    listing.source,
                    listing.external_id,
                ),
            )

        conn.execute(
            """
            INSERT INTO listing_snapshots
            (source, external_id, price, shipping, currency, scan_run_id, event_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                listing.source,
                listing.external_id,
                listing.price,
                listing.shipping,
                listing.currency,
                scan_run_id,
                event_type,
            ),
        )

        if event_type != "UNCHANGED":
            conn.execute(
                """
                INSERT INTO listing_events
                (scan_run_id, source, external_id, event_type, old_price, new_price, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scan_run_id,
                    listing.source,
                    listing.external_id,
                    event_type,
                    old_price,
                    listing.price,
                    json.dumps({"title": listing.title}),
                ),
            )

    return event_type


def mark_missing_listings(
    source: str,
    sport: str,
    observed_external_ids: set[str],
    scan_run_id: int,
    missing_threshold: int,
) -> dict[str, int]:
    missing = 0
    inactive = 0

    with session() as conn:
        rows = conn.execute(
            """
            SELECT external_id, current_price, missed_scan_count, active
            FROM listings
            WHERE source=?
              AND sport=?
              AND active=1
            """,
            (source, sport.upper()),
        ).fetchall()

        for row in rows:
            external_id = row["external_id"]
            if external_id in observed_external_ids:
                continue

            missing += 1
            missed_count = int(row["missed_scan_count"] or 0) + 1
            event_type = "MISSING_FROM_SCAN"
            active = 1

            if missed_count >= missing_threshold:
                event_type = "INACTIVE"
                active = 0
                inactive += 1

            conn.execute(
                """
                UPDATE listings
                SET missed_scan_count=?,
                    active=?,
                    last_scan_run_id=?,
                    last_change_type=?
                WHERE source=? AND external_id=?
                """,
                (
                    missed_count,
                    active,
                    scan_run_id,
                    event_type,
                    source,
                    external_id,
                ),
            )
            conn.execute(
                """
                INSERT INTO listing_events
                (scan_run_id, source, external_id, event_type, old_price, new_price, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scan_run_id,
                    source,
                    external_id,
                    event_type,
                    row["current_price"],
                    row["current_price"],
                    json.dumps({"missed_scan_count": missed_count}),
                ),
            )

    return {
        "missing": missing,
        "inactive": inactive,
    }


def fetch_listings(
    source: str,
    sport: str,
    limit: int,
) -> list[Listing]:
    sql = """
        SELECT *
        FROM listings
        WHERE source=?
    """
    params: list[object] = [source]

    if sport.upper() != "ALL":
        sql += " AND sport=?"
        params.append(sport.upper())

    sql += " ORDER BY id LIMIT ?"
    params.append(int(limit))

    with session() as conn:
        rows = conn.execute(sql, params).fetchall()

    listings: list[Listing] = []

    for row in rows:
        identity = (
            CardIdentity.model_validate_json(row["identity_json"])
            if row["identity_json"]
            else None
        )
        listings.append(
            Listing(
                source=row["source"],
                external_id=row["external_id"],
                url=row["url"],
                title=row["title"],
                sport=row["sport"],
                price=row["price"],
                currency=row["currency"],
                shipping=row["shipping"],
                image_url=row["image_url"],
                seller=row["seller"],
                condition=row["condition"],
                discovered_at=row["discovered_at"],
                identity=identity,
            )
        )

    return listings


def upsert_market_listing(listing: MarketListing):
    with session() as conn:
        conn.execute(
            """
            INSERT INTO market_listings
            (source, external_id, title, url, price, currency, shipping, seller,
             condition, buying_option, image_url, marketplace, discovered_at,
             identity_json, risk_flags_json, landed_price_aud, fx_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, external_id) DO UPDATE SET
                title=excluded.title,
                url=excluded.url,
                price=excluded.price,
                currency=excluded.currency,
                shipping=excluded.shipping,
                seller=excluded.seller,
                condition=excluded.condition,
                buying_option=excluded.buying_option,
                image_url=excluded.image_url,
                marketplace=excluded.marketplace,
                last_seen=CURRENT_TIMESTAMP,
                identity_json=excluded.identity_json,
                risk_flags_json=excluded.risk_flags_json,
                landed_price_aud=excluded.landed_price_aud,
                fx_status=excluded.fx_status
            """,
            (
                listing.source,
                listing.external_id,
                listing.title,
                listing.url,
                listing.price,
                listing.currency,
                listing.shipping,
                listing.seller,
                listing.condition,
                listing.buying_option,
                listing.image_url,
                listing.marketplace,
                listing.discovered_at.isoformat(),
                listing.identity.model_dump_json() if listing.identity else None,
                json.dumps(listing.risk_flags),
                listing.landed_price_aud,
                listing.fx_status,
            ),
        )
        conn.execute(
            """
            INSERT INTO market_listing_snapshots
            (source, external_id, price, shipping, currency, landed_price_aud, fx_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                listing.source,
                listing.external_id,
                listing.price,
                listing.shipping,
                listing.currency,
                listing.landed_price_aud,
                listing.fx_status,
            ),
        )


def save_market_match(
    match: MarketMatch,
    scan_run_id: int | None = None,
):
    with session() as conn:
        conn.execute(
            """
            INSERT INTO market_matches
            (scan_run_id, source_listing_external_id, market_source,
             market_external_id, match_level, match_score, match_reasons_json,
             rejection_reasons_json, risk_flags_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(scan_run_id, source_listing_external_id, market_source, market_external_id)
            DO UPDATE SET
                match_level=excluded.match_level,
                match_score=excluded.match_score,
                match_reasons_json=excluded.match_reasons_json,
                rejection_reasons_json=excluded.rejection_reasons_json,
                risk_flags_json=excluded.risk_flags_json
            """,
            (
                scan_run_id,
                match.source_listing_external_id,
                match.market_source,
                match.market_external_id,
                match.match_level.value,
                match.match_score,
                json.dumps(match.match_reasons),
                json.dumps(match.rejection_reasons),
                json.dumps(match.risk_flags),
            ),
        )


def save_market_metrics(
    metrics: ActiveMarketMetrics,
    scan_run_id: int | None = None,
):
    with session() as conn:
        conn.execute(
            """
            INSERT INTO market_metrics
            (scan_run_id, source_listing_external_id, active_match_count,
             active_exact_count, active_strong_count, active_lowest_aud,
             active_median_aud, active_trimmed_median_aud, active_mean_aud,
             active_max_aud, active_market_spread, cherry_vs_active_lowest_pct,
             cherry_vs_active_median_pct, market_match_confidence, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scan_run_id,
                metrics.source_listing_external_id,
                metrics.active_match_count,
                metrics.active_exact_count,
                metrics.active_strong_count,
                metrics.active_lowest_aud,
                metrics.active_median_aud,
                metrics.active_trimmed_median_aud,
                metrics.active_mean_aud,
                metrics.active_max_aud,
                metrics.active_market_spread,
                metrics.cherry_vs_active_lowest_pct,
                metrics.cherry_vs_active_median_pct,
                metrics.market_match_confidence,
                metrics.status,
            ),
        )


def upsert_sold_comp(comp: SoldComp):
    with session() as conn:
        conn.execute(
            """
            INSERT INTO sold_comps
            (source, sale_id, sold_date, title, sold_price, currency, shipping,
             sold_price_aud, sale_type, url, notes, identity_json, imported_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, sale_id) DO UPDATE SET
                sold_date=excluded.sold_date,
                title=excluded.title,
                sold_price=excluded.sold_price,
                currency=excluded.currency,
                shipping=excluded.shipping,
                sold_price_aud=excluded.sold_price_aud,
                sale_type=excluded.sale_type,
                url=excluded.url,
                notes=excluded.notes,
                identity_json=excluded.identity_json
            """,
            (
                comp.source,
                comp.sale_id,
                comp.sold_date,
                comp.title,
                comp.sold_price,
                comp.currency,
                comp.shipping,
                comp.sold_price_aud,
                comp.sale_type,
                comp.url,
                comp.notes,
                comp.identity.model_dump_json() if comp.identity else None,
                comp.imported_at.isoformat(),
            ),
        )


def sold_comp_exists(source: str, sale_id: str) -> bool:
    with session() as conn:
        row = conn.execute(
            """
            SELECT id
            FROM sold_comps
            WHERE source=? AND sale_id=?
            """,
            (source, sale_id),
        ).fetchone()

    return row is not None


def fetch_sold_comps(limit: int = 100) -> list[sqlite3.Row]:
    with session() as conn:
        return conn.execute(
            """
            SELECT c.*,
                   COUNT(m.id) AS match_count,
                   SUM(CASE WHEN m.match_level='EXACT' THEN 1 ELSE 0 END) AS exact_matches,
                   SUM(CASE WHEN m.match_level='STRONG' THEN 1 ELSE 0 END) AS strong_matches,
                   SUM(CASE WHEN m.match_level='RELATED' THEN 1 ELSE 0 END) AS related_matches
            FROM sold_comps c
            LEFT JOIN sold_comp_matches m
              ON m.sold_source=c.source
             AND m.sale_id=c.sale_id
            GROUP BY c.id
            ORDER BY c.imported_at DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()


def save_sold_comp_match(match: SoldCompMatch):
    with session() as conn:
        conn.execute(
            """
            INSERT INTO sold_comp_matches
            (source_listing_external_id, sold_source, sale_id, match_level,
             match_score, match_reasons_json, rejection_reasons_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_listing_external_id, sold_source, sale_id)
            DO UPDATE SET
                match_level=excluded.match_level,
                match_score=excluded.match_score,
                match_reasons_json=excluded.match_reasons_json,
                rejection_reasons_json=excluded.rejection_reasons_json
            """,
            (
                match.source_listing_external_id,
                match.sold_source,
                match.sale_id,
                match.match_level.value,
                match.match_score,
                json.dumps(match.match_reasons),
                json.dumps(match.rejection_reasons),
            ),
        )


def fetch_sold_comps_for_listing(
    source_listing_external_id: str,
) -> list[tuple[SoldComp, SoldCompMatch]]:
    with session() as conn:
        rows = conn.execute(
            """
            SELECT
                c.*,
                m.match_level,
                m.match_score,
                m.match_reasons_json,
                m.rejection_reasons_json
            FROM sold_comp_matches m
            JOIN sold_comps c
              ON c.source=m.sold_source
             AND c.sale_id=m.sale_id
            WHERE m.source_listing_external_id=?
            ORDER BY c.sold_date DESC
            """,
            (source_listing_external_id,),
        ).fetchall()

    results: list[tuple[SoldComp, SoldCompMatch]] = []

    for row in rows:
        identity = (
            CardIdentity.model_validate_json(row["identity_json"])
            if row["identity_json"]
            else None
        )
        comp = SoldComp(
            source=row["source"],
            sale_id=row["sale_id"],
            sold_date=row["sold_date"],
            title=row["title"],
            sold_price=row["sold_price"],
            currency=row["currency"],
            shipping=row["shipping"],
            sold_price_aud=row["sold_price_aud"],
            sale_type=row["sale_type"],
            url=row["url"],
            notes=row["notes"],
            identity=identity,
            imported_at=row["imported_at"],
        )
        match = SoldCompMatch(
            source_listing_external_id=source_listing_external_id,
            sold_source=row["source"],
            sale_id=row["sale_id"],
            match_level=row["match_level"],
            match_score=row["match_score"],
            match_reasons=json.loads(row["match_reasons_json"] or "[]"),
            rejection_reasons=json.loads(row["rejection_reasons_json"] or "[]"),
        )
        results.append((comp, match))

    return results


def save_sold_valuation(valuation: SoldValuation):
    with session() as conn:
        conn.execute(
            """
            INSERT INTO sold_valuations
            (source_listing_external_id, sold_comp_count, exact_comp_count,
             strong_comp_count, related_comp_count, latest_sale_aud,
             median_sale_aud, weighted_median_aud, trimmed_mean_aud,
             median_30_day_aud, median_90_day_aud, median_180_day_aud,
             fair_value_aud, quick_sale_value_aud, liquidity_score,
             comp_confidence, market_direction, market_direction_reason,
             status, explanation_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                valuation.source_listing_external_id,
                valuation.sold_comp_count,
                valuation.exact_comp_count,
                valuation.strong_comp_count,
                valuation.related_comp_count,
                valuation.latest_sale_aud,
                valuation.median_sale_aud,
                valuation.weighted_median_aud,
                valuation.trimmed_mean_aud,
                valuation.median_30_day_aud,
                valuation.median_90_day_aud,
                valuation.median_180_day_aud,
                valuation.fair_value_aud,
                valuation.quick_sale_value_aud,
                valuation.liquidity_score,
                valuation.comp_confidence,
                valuation.market_direction,
                valuation.market_direction_reason,
                valuation.status,
                json.dumps(valuation.explanation),
            ),
        )


def save_opportunity(opportunity: Opportunity):
    with session() as conn:
        conn.execute(
            """
            INSERT INTO opportunities
            (source_listing_external_id, landed_cost_aud, fair_value_aud,
             quick_sale_value_aud, edge_pct, opportunity_score,
             identity_confidence, comp_confidence, liquidity_score,
             risk_score, market_direction, status, reasons_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                opportunity.source_listing_external_id,
                opportunity.landed_cost_aud,
                opportunity.fair_value_aud,
                opportunity.quick_sale_value_aud,
                opportunity.edge_pct,
                opportunity.opportunity_score,
                opportunity.identity_confidence,
                opportunity.comp_confidence,
                opportunity.liquidity_score,
                opportunity.risk_score,
                opportunity.market_direction,
                opportunity.status,
                json.dumps(opportunity.reasons),
            ),
        )


def latest_opportunities(
    sport: str,
    limit: int,
) -> list[sqlite3.Row]:
    sql = """
        SELECT o.*, l.sport, l.title, l.price, l.currency, l.identity_json,
               v.sold_comp_count
        FROM opportunities o
        JOIN listings l
          ON l.external_id=o.source_listing_external_id
         AND l.source='cherry'
        LEFT JOIN sold_valuations v
          ON v.source_listing_external_id=o.source_listing_external_id
         AND v.id IN (
             SELECT MAX(id)
             FROM sold_valuations
             GROUP BY source_listing_external_id
         )
        WHERE l.active=1
          AND o.id IN (
              SELECT MAX(id)
              FROM opportunities
              GROUP BY source_listing_external_id
          )
    """
    params: list[object] = []

    if sport.upper() != "ALL":
        sql += " AND l.sport=?"
        params.append(sport.upper())

    sql += " ORDER BY o.opportunity_score DESC LIMIT ?"
    params.append(int(limit))

    with session() as conn:
        return conn.execute(sql, params).fetchall()


def listing_events(
    event_type: str | None = None,
    sport: str = "ALL",
    limit: int = 50,
) -> list[sqlite3.Row]:
    sql = """
        SELECT e.*, l.sport, l.title, l.identity_json
        FROM listing_events e
        LEFT JOIN listings l
          ON l.source=e.source
         AND l.external_id=e.external_id
        WHERE e.source='cherry'
    """
    params: list[object] = []

    if event_type:
        sql += " AND e.event_type=?"
        params.append(event_type)

    if sport.upper() != "ALL":
        sql += " AND l.sport=?"
        params.append(sport.upper())

    sql += " ORDER BY e.id DESC LIMIT ?"
    params.append(int(limit))

    with session() as conn:
        return conn.execute(sql, params).fetchall()


def latest_sold_valuations(
    status: str | None = None,
    sport: str = "ALL",
    limit: int = 50,
) -> list[sqlite3.Row]:
    sql = """
        SELECT v.*, l.sport, l.title, l.identity_json
        FROM sold_valuations v
        JOIN listings l
          ON l.external_id=v.source_listing_external_id
         AND l.source='cherry'
        WHERE v.id IN (
            SELECT MAX(id)
            FROM sold_valuations
            GROUP BY source_listing_external_id
        )
    """
    params: list[object] = []

    if status:
        sql += " AND v.status=?"
        params.append(status)

    if sport.upper() != "ALL":
        sql += " AND l.sport=?"
        params.append(sport.upper())

    sql += " ORDER BY v.sold_comp_count ASC, v.created_at DESC LIMIT ?"
    params.append(int(limit))

    with session() as conn:
        return conn.execute(sql, params).fetchall()


def add_watch_item(item: WatchItem) -> int:
    with session() as conn:
        conn.execute(
            """
            INSERT INTO watch_items(watch_type, value, sport, label, active)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(watch_type, value, sport) DO UPDATE SET
                label=excluded.label,
                active=1
            """,
            (
                item.watch_type,
                item.value,
                item.sport,
                item.label,
            ),
        )
        row = conn.execute(
            """
            SELECT id
            FROM watch_items
            WHERE watch_type=?
              AND value=?
              AND (sport IS ? OR sport=?)
            """,
            (item.watch_type, item.value, item.sport, item.sport),
        ).fetchone()

        return int(row["id"])


def remove_watch_item(watch_id: int) -> bool:
    with session() as conn:
        cursor = conn.execute(
            """
            UPDATE watch_items
            SET active=0
            WHERE id=?
            """,
            (watch_id,),
        )

    return cursor.rowcount > 0


def list_watch_items(include_inactive: bool = False) -> list[sqlite3.Row]:
    sql = "SELECT * FROM watch_items"
    if not include_inactive:
        sql += " WHERE active=1"
    sql += " ORDER BY id"

    with session() as conn:
        return conn.execute(sql).fetchall()


def record_watch_event(event: WatchEvent):
    with session() as conn:
        conn.execute(
            """
            INSERT INTO watch_events
            (watch_item_id, event_type, source, external_id, details_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event.watch_item_id,
                event.event_type,
                event.source,
                event.external_id,
                json.dumps(event.details),
            ),
        )


def watch_event_history(limit: int = 50) -> list[sqlite3.Row]:
    with session() as conn:
        return conn.execute(
            """
            SELECT e.*, w.watch_type, w.value, w.sport, w.label
            FROM watch_events e
            LEFT JOIN watch_items w
              ON w.id=e.watch_item_id
            ORDER BY e.id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()

def save_valuation(v: Valuation):
    with session() as conn:
        conn.execute(
            """
            INSERT INTO valuations
            (external_id, landed_cost_aud, fair_value_aud, quick_sale_value_aud,
             comp_count, comp_confidence, liquidity, identity_confidence,
             risk_penalty, opportunity_score, edge_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                v.listing_external_id, v.landed_cost_aud, v.fair_value_aud,
                v.quick_sale_value_aud, v.comp_count, v.comp_confidence,
                v.liquidity, v.identity_confidence, v.risk_penalty,
                v.opportunity_score, v.edge_pct,
            ),
        )
