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
    UNIQUE(source, external_id)
);

CREATE TABLE IF NOT EXISTS listing_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    price REAL NOT NULL,
    shipping REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL
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

CREATE INDEX IF NOT EXISTS idx_market_matches_listing ON market_matches(source_listing_external_id);
CREATE INDEX IF NOT EXISTS idx_market_metrics_listing ON market_metrics(source_listing_external_id);
CREATE INDEX IF NOT EXISTS idx_sold_comp_matches_listing ON sold_comp_matches(source_listing_external_id);
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

def init_db():
    with session() as conn:
        conn.executescript(SCHEMA)


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

def upsert_listing(listing: Listing):
    with session() as conn:
        conn.execute(
            """
            INSERT INTO listings
            (source, external_id, url, title, sport, price, currency, shipping,
             image_url, seller, condition, discovered_at, identity_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                identity_json=excluded.identity_json
            """,
            (
                listing.source, listing.external_id, listing.url, listing.title,
                listing.sport, listing.price, listing.currency, listing.shipping,
                listing.image_url, listing.seller, listing.condition,
                listing.discovered_at.isoformat(),
                listing.identity.model_dump_json() if listing.identity else None,
            ),
        )


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
        conn.execute(
            """
            INSERT INTO listing_snapshots(source, external_id, price, shipping, currency)
            VALUES (?, ?, ?, ?, ?)
            """,
            (listing.source, listing.external_id, listing.price, listing.shipping, listing.currency),
        )

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
