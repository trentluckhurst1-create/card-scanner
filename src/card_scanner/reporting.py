from __future__ import annotations

import csv
from pathlib import Path

from rich.table import Table

from .db import latest_opportunities, latest_sold_valuations, listing_events
from .models import CardIdentity


def _identity(row) -> CardIdentity | None:
    if not row["identity_json"]:
        return None

    return CardIdentity.model_validate_json(row["identity_json"])


def _write_csv(path: str | None, rows: list[dict]):
    if not path:
        return

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else ["message"]

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def opportunities_table(
    sport: str,
    limit: int,
    export_csv: str | None = None,
) -> Table:
    rows = latest_opportunities(sport, limit)
    table = Table(title="Top Opportunities")
    columns = [
        "SPORT",
        "PLAYER",
        "CARD",
        "CHERRY_PRICE",
        "FAIR_VALUE",
        "QUICK_SALE",
        "EDGE",
        "SOLD_COMPS",
        "COMP_CONF",
        "LIQUIDITY",
        "RISK",
        "TREND",
        "STATUS",
    ]
    for column in columns:
        table.add_column(column)

    csv_rows: list[dict] = []

    for row in rows:
        identity = _identity(row)
        output = {
            "SPORT": row["sport"],
            "PLAYER": identity.player if identity and identity.player else "",
            "CARD": row["title"],
            "CHERRY_PRICE": row["price"],
            "FAIR_VALUE": row["fair_value_aud"],
            "QUICK_SALE": row["quick_sale_value_aud"],
            "EDGE": row["edge_pct"],
            "SOLD_COMPS": row["sold_comp_count"],
            "COMP_CONF": row["comp_confidence"],
            "LIQUIDITY": row["liquidity_score"],
            "RISK": row["risk_score"],
            "TREND": row["market_direction"],
            "STATUS": row["status"],
        }
        csv_rows.append(output)
        table.add_row(*(str(output[column] or "") for column in columns))

    _write_csv(export_csv, csv_rows)

    return table


def events_table(
    event_type: str,
    sport: str,
    limit: int,
    export_csv: str | None = None,
) -> Table:
    rows = listing_events(event_type, sport, limit)
    table = Table(title=event_type.replace("_", " ").title())
    columns = ["EVENT", "SPORT", "PLAYER", "TITLE", "OLD_PRICE", "NEW_PRICE", "AT"]
    for column in columns:
        table.add_column(column)

    csv_rows: list[dict] = []

    for row in rows:
        identity = _identity(row)
        output = {
            "EVENT": row["event_type"],
            "SPORT": row["sport"],
            "PLAYER": identity.player if identity and identity.player else "",
            "TITLE": row["title"],
            "OLD_PRICE": row["old_price"],
            "NEW_PRICE": row["new_price"],
            "AT": row["created_at"],
        }
        csv_rows.append(output)
        table.add_row(*(str(output[column] or "") for column in columns))

    _write_csv(export_csv, csv_rows)

    return table


def insufficient_comps_table(
    sport: str,
    limit: int,
    export_csv: str | None = None,
) -> Table:
    rows = latest_sold_valuations("INSUFFICIENT_SOLD_COMPS", sport, limit)
    table = Table(title="Insufficient Sold Comps")
    columns = ["SPORT", "PLAYER", "TITLE", "SOLD_COMPS", "STATUS"]
    for column in columns:
        table.add_column(column)

    csv_rows: list[dict] = []

    for row in rows:
        identity = _identity(row)
        output = {
            "SPORT": row["sport"],
            "PLAYER": identity.player if identity and identity.player else "",
            "TITLE": row["title"],
            "SOLD_COMPS": row["sold_comp_count"],
            "STATUS": row["status"],
        }
        csv_rows.append(output)
        table.add_row(*(str(output[column] or "") for column in columns))

    _write_csv(export_csv, csv_rows)

    return table
