from __future__ import annotations
import csv
import typer
from rich.console import Console
from rich.table import Table

from .cherry_collector import CherryCollector
from .db import (
    fetch_listings,
    fetch_sold_comps,
    fetch_sold_comps_for_listing,
    finish_scan_run,
    init_db,
    list_watch_items,
    save_opportunity,
    save_sold_valuation,
    start_scan_run,
    upsert_listing,
    save_valuation,
    watch_event_history,
)
from .identity_audit import audit_identities
from .identity import parse_identity
from .market_engine import MarketEngine
from .models import Listing
from .opportunity import assess_opportunity
from .reporting import events_table, insufficient_comps_table, opportunities_table
from .risk import title_risk_details
from .scoring import score_listing
from .sold_comps import import_sold_comp_csv
from .sources.ebay import EbaySource
from .sources.cherry import CherrySource
from .valuation import value_from_sold_comps
from .sold_comp_engine import EphemeralSoldCompEngine
from .the_card_api import TheCardApiSoldCompProvider
from .watchlist import add_watch, remove_watch

app = typer.Typer(no_args_is_help=True)
console = Console()

@app.command("init-db")
def init_db_cmd():
    init_db()
    console.print("[green]Database initialized.[/green]")

@app.command()
def demo():
    """Runs the scoring engine on synthetic examples so no credentials are needed."""
    init_db()
    examples = [
        ("NFL", "2025 Prizm Football Example Player Rookie Auto Gold /50", 180, 290, 8, .91, .76, .92),
        ("NBA", "2025 Select Example Player RC Courtside Gold /10", 260, 300, 3, .68, .62, .80),
        ("MLB", "2025 Bowman Chrome Example Prospect 1st Bowman Auto Gold /50", 145, 260, 7, .88, .81, .91),
        ("AFL", "2025 Select AFL Example Player Rookie Signature Auto /70", 120, 190, 5, .78, .55, .89),
    ]

    table = Table(title="CARD SCANNER V1 — DEMO")
    for col in ["Sport", "Listing", "Cost", "Fair", "Edge", "Score"]:
        table.add_column(col)

    for i, (sport, title, cost, fair, comps, conf, liq, ident) in enumerate(examples, start=1):
        listing = Listing(
            source="demo", external_id=f"DEMO-{i}", url="https://example.invalid",
            title=title, sport=sport, price=cost, identity=parse_identity(title, sport)
        )
        upsert_listing(listing)
        v = score_listing(listing, fair, fair * .9, comps, conf, liq, ident)
        save_valuation(v)
        table.add_row(
            sport, title, f"A${cost:.2f}", f"A${fair:.2f}",
            f"{v.edge_pct:.1f}%", f"{v.opportunity_score:.1f}"
        )
    console.print(table)

@app.command("scan-ebay")
def scan_ebay(
    sport: str = typer.Option(..., help="NFL, NBA, MLB or AFL"),
    query: str = typer.Option(...),
    limit: int = typer.Option(50),
):
    init_db()
    source = EbaySource()
    items = source.search(sport, query, limit)
    for item in items:
        upsert_listing(item)
    console.print(f"[green]Stored {len(items)} eBay listings for {sport.upper()}.[/green]")

@app.command("scan-cherry")
def scan_cherry(
    sport: str = typer.Option(..., help="NFL, NBA, MLB or AFL"),
    query: str = typer.Option("", help="Optional local title filter"),
    limit: int = typer.Option(50),
):
    init_db()
    source = CherrySource()
    items = source.search(sport, query, limit)
    for item in items:
        upsert_listing(item)
    console.print(f"[green]Stored {len(items)} Cherry listings for {sport.upper()}.[/green]")


@app.command("scan-cherry-all")
def scan_cherry_all(
    sport: str = typer.Option(..., help="NFL, NBA, MLB, AFL or ALL"),
    force: bool = typer.Option(False, help="Ignore CHERRY_SCAN_CACHE_MINUTES"),
    page_size: int | None = typer.Option(None, help="Override CHERRY_PAGE_SIZE"),
    max_products: int | None = typer.Option(None, help="Override CHERRY_MAX_PRODUCTS_PER_SPORT"),
):
    init_db()
    sports = ["NFL", "NBA", "MLB", "AFL"] if sport.upper() == "ALL" else [sport.upper()]
    collector = CherryCollector(
        page_size=page_size,
        max_products_per_sport=max_products,
    )
    table = Table(title="Cherry Full Ingestion")

    for column in [
        "SPORT",
        "FETCHED",
        "NEW",
        "UPDATED",
        "UNCHANGED",
        "PRICE_DROPS",
        "PRICE_RISES",
        "MISSING",
        "INACTIVE",
        "ERRORS",
        "STATUS",
    ]:
        table.add_column(column)

    for sport_name in sports:
        summary = collector.scan_sport(sport_name, force=force)
        status = "CACHE_SKIP" if summary.skipped_cache else "PASS"
        if summary.errors:
            status = "PARTIAL"
        table.add_row(
            summary.sport,
            str(summary.fetched),
            str(summary.new),
            str(summary.updated),
            str(summary.unchanged),
            str(summary.price_drops),
            str(summary.price_rises),
            str(summary.missing),
            str(summary.inactive),
            str(summary.errors),
            status,
        )

    console.print(table)


@app.command("audit-identities")
def audit_identities_cmd(
    source: str = typer.Option("cherry"),
    sport: str = typer.Option("ALL", help="NFL, NBA, MLB, AFL or ALL"),
    limit: int = typer.Option(10000),
):
    init_db()
    listings = fetch_listings(source, sport.upper(), limit)
    summary = audit_identities(listings)
    console.print(f"TOTAL_LISTINGS={summary.total}")
    console.print(f"PLAYER_COVERAGE={summary.player_coverage:.2f}%")
    console.print(f"YEAR_COVERAGE={summary.year_coverage:.2f}%")
    console.print(f"SET_COVERAGE={summary.set_coverage:.2f}%")
    console.print(f"PARALLEL_COVERAGE={summary.parallel_coverage:.2f}%")
    console.print(f"SERIAL_COVERAGE={summary.serial_coverage:.2f}%")
    console.print(f"CARD_NUMBER_COVERAGE={summary.card_number_coverage:.2f}%")
    console.print(f"GRADE_COVERAGE={summary.grade_coverage:.2f}%")
    console.print(f"COMP_READY_RATE={summary.comp_ready_rate:.2f}%")

    table = Table(title="Lowest Confidence Identities")
    for column in ["SPORT", "CONF", "PLAYER", "TITLE", "EXPLANATION"]:
        table.add_column(column)

    for row in summary.lowest_confidence:
        identity = row.identity
        table.add_row(
            row.sport,
            f"{row.confidence:.3f}",
            identity.player if identity and identity.player else "",
            row.title[:80],
            "; ".join(row.explanations[:6]),
        )

    console.print(table)

@app.command("scan-market")
def scan_market(
    source: str = typer.Option("cherry", help="Currently supported: cherry"),
    sport: str = typer.Option(..., help="NFL, NBA, MLB, AFL or ALL"),
    limit: int = typer.Option(20, help="Listings per sport"),
):
    init_db()
    source = source.lower()
    sport = sport.upper()

    if source != "cherry":
        console.print("[red]scan-market currently supports --source cherry only.[/red]")
        raise typer.Exit(2)

    sports = ["NFL", "NBA", "MLB", "AFL"] if sport == "ALL" else [sport]
    scan_run_id = start_scan_run(source, sport)
    cherry = CherrySource()
    engine = MarketEngine()
    missing_credentials = engine.market_source.missing_credentials()

    if missing_credentials:
        message = (
            "Missing required eBay credentials: "
            + ", ".join(missing_credentials)
        )
        finish_scan_run(scan_run_id, "FAILED", message)
        console.print(f"[red]{message}[/red]")
        console.print("Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET in .env.")
        raise typer.Exit(1)

    results = []

    try:
        for sport_name in sports:
            listings = cherry.search(sport_name, "", limit)
            for listing in listings:
                upsert_listing(listing)
                results.append(engine.scan_listing(listing, scan_run_id))
    except RuntimeError as exc:
        finish_scan_run(scan_run_id, "FAILED", str(exc))
        console.print(f"[red]{exc}[/red]")
        if "EBAY_CLIENT_ID" in str(exc) or "EBAY_CLIENT_SECRET" in str(exc):
            console.print("Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET in .env.")
        raise typer.Exit(1)

    finish_scan_run(
        scan_run_id,
        "PASS",
        f"queries={engine.query_count}",
    )

    table = Table(title="CARD SCANNER MARKET ENGINE - ACTIVE ASKING MARKET")
    for column in [
        "SPORT",
        "PLAYER",
        "CARD",
        "CHERRY_PRICE_AUD",
        "ACTIVE_MATCHES",
        "ACTIVE_LOWEST_AUD",
        "ACTIVE_MEDIAN_AUD",
        "DISCOUNT_TO_LOWEST",
        "DISCOUNT_TO_MEDIAN",
        "IDENTITY_QUALITY",
        "MARKET_MATCH_CONFIDENCE",
        "STATUS",
    ]:
        table.add_column(column)

    for result in results:
        identity = result.listing.identity
        metrics = result.metrics
        card = result.exact_query or result.listing.title
        table.add_row(
            result.listing.sport,
            identity.player if identity and identity.player else "",
            card[:70],
            f"A${result.listing.price + result.listing.shipping:.2f}",
            str(metrics.active_match_count),
            f"A${metrics.active_lowest_aud:.2f}" if metrics.active_lowest_aud is not None else "",
            f"A${metrics.active_median_aud:.2f}" if metrics.active_median_aud is not None else "",
            f"{metrics.cherry_vs_active_lowest_pct:.1f}%" if metrics.cherry_vs_active_lowest_pct is not None else "",
            f"{metrics.cherry_vs_active_median_pct:.1f}%" if metrics.cherry_vs_active_median_pct is not None else "",
            f"{result.identity_quality:.3f}",
            f"{metrics.market_match_confidence:.3f}",
            metrics.status,
        )

    console.print(table)
    console.print("[yellow]BUY output is disabled until genuine sold comps are available.[/yellow]")


@app.command("import-sold-comps")
def import_sold_comps_cmd(
    csv_path: str = typer.Option(..., "--csv", help="Manual sold-comp CSV path"),
    sport: str = typer.Option(..., help="NFL, NBA, MLB, AFL or ALL"),
):
    init_db()
    result = import_sold_comp_csv(csv_path, sport.upper())
    console.print(
        f"[green]Imported {result.imported} sold comps and saved {result.matches_saved} comparable matches.[/green]"
    )
    console.print(f"DUPLICATES_IN_FILE={result.duplicates_in_file}")
    console.print(f"DUPLICATES_EXISTING={result.duplicates_existing}")
    console.print(f"INVALID_DATES={result.invalid_dates}")
    console.print(f"INVALID_PRICES={result.invalid_prices}")
    console.print(f"MISSING_CURRENCY={result.missing_currency}")
    console.print(f"MISSING_AUD_CONVERSION={result.missing_aud_conversion}")

    if result.errors:
        for error in result.errors[:10]:
            console.print(f"[yellow]{error}[/yellow]")


@app.command("audit-sold-comps")
def audit_sold_comps_cmd(
    limit: int = typer.Option(50),
):
    init_db()
    table = Table(title="Sold Comp Import Audit")
    for column in ["SOURCE", "SALE_ID", "SOLD_DATE", "PRICE", "AUD", "MATCHES", "EXACT", "STRONG", "RELATED", "TITLE"]:
        table.add_column(column)

    for row in fetch_sold_comps(limit):
        table.add_row(
            row["source"],
            row["sale_id"],
            row["sold_date"],
            f"{row['currency']} {row['sold_price']:.2f}",
            f"A${row['sold_price_aud']:.2f}" if row["sold_price_aud"] is not None else "FX_PENDING",
            str(row["match_count"] or 0),
            str(row["exact_matches"] or 0),
            str(row["strong_matches"] or 0),
            str(row["related_matches"] or 0),
            row["title"][:70],
        )

    console.print(table)


@app.command("value-sold-comps")
def value_sold_comps_cmd(
    sport: str = typer.Option("ALL", help="NFL, NBA, MLB, AFL or ALL"),
    limit: int = typer.Option(10000),
):
    init_db()
    listings = fetch_listings("cherry", sport.upper(), limit)
    valued = 0

    for listing in listings:
        valuation = value_from_sold_comps(
            listing.external_id,
            fetch_sold_comps_for_listing(listing.external_id),
        )
        save_sold_valuation(valuation)
        opportunity = assess_opportunity(
            listing,
            valuation,
            title_risk_details(listing.title),
        )
        save_opportunity(opportunity)
        valued += 1

    console.print(f"[green]VALUED_LISTINGS={valued}[/green]")


@app.command("opportunities")
def opportunities_cmd(
    sport: str = typer.Option("ALL"),
    limit: int = typer.Option(50),
    export_csv: str | None = typer.Option(None, "--export-csv"),
):
    init_db()
    console.print(opportunities_table(sport.upper(), limit, export_csv))


@app.command("new-cherry-listings")
def new_cherry_listings_cmd(
    sport: str = typer.Option("ALL"),
    limit: int = typer.Option(50),
    export_csv: str | None = typer.Option(None, "--export-csv"),
):
    init_db()
    console.print(events_table("NEW_LISTING", sport.upper(), limit, export_csv))


@app.command("price-drops")
def price_drops_cmd(
    sport: str = typer.Option("ALL"),
    limit: int = typer.Option(50),
    export_csv: str | None = typer.Option(None, "--export-csv"),
):
    init_db()
    console.print(events_table("PRICE_DROP", sport.upper(), limit, export_csv))


@app.command("insufficient-comps")
def insufficient_comps_cmd(
    sport: str = typer.Option("ALL"),
    limit: int = typer.Option(50),
    export_csv: str | None = typer.Option(None, "--export-csv"),
):
    init_db()
    console.print(insufficient_comps_table(sport.upper(), limit, export_csv))


@app.command("identity-failures")
def identity_failures_cmd(
    sport: str = typer.Option("ALL"),
    limit: int = typer.Option(50),
):
    init_db()
    listings = fetch_listings("cherry", sport.upper(), 10000)
    summary = audit_identities(listings, low_confidence_limit=limit)
    table = Table(title="Identity Failures / Low Confidence")
    for column in ["SPORT", "CONF", "TITLE", "EXPLANATION"]:
        table.add_column(column)

    for row in summary.lowest_confidence:
        table.add_row(
            row.sport,
            f"{row.confidence:.3f}",
            row.title[:90],
            "; ".join(row.explanations),
        )

    console.print(table)


@app.command("watch-add")
def watch_add_cmd(
    watch_type: str = typer.Option(..., help="listing, player, identity_signature or query"),
    value: str = typer.Option(...),
    sport: str | None = typer.Option(None),
    label: str | None = typer.Option(None),
):
    init_db()
    watch_id = add_watch(watch_type, value, sport, label)
    console.print(f"[green]WATCH_ID={watch_id}[/green]")


@app.command("watch-remove")
def watch_remove_cmd(
    watch_id: int = typer.Option(...),
):
    init_db()
    removed = remove_watch(watch_id)
    console.print("REMOVED=YES" if removed else "REMOVED=NO")


@app.command("watch-list")
def watch_list_cmd(
    include_inactive: bool = typer.Option(False),
):
    init_db()
    table = Table(title="Watchlist")
    for column in ["ID", "TYPE", "SPORT", "VALUE", "LABEL", "ACTIVE"]:
        table.add_column(column)

    for row in list_watch_items(include_inactive):
        table.add_row(
            str(row["id"]),
            row["watch_type"],
            row["sport"] or "",
            row["value"],
            row["label"] or "",
            "YES" if row["active"] else "NO",
        )

    console.print(table)


@app.command("watch-history")
def watch_history_cmd(
    limit: int = typer.Option(50),
):
    init_db()
    table = Table(title="Watch Event History")
    for column in ["AT", "EVENT", "TYPE", "VALUE", "SOURCE", "EXTERNAL_ID"]:
        table.add_column(column)

    for row in watch_event_history(limit):
        table.add_row(
            row["created_at"],
            row["event_type"],
            row["watch_type"] or "",
            row["value"] or "",
            row["source"] or "",
            row["external_id"] or "",
        )

    console.print(table)


@app.command("live-sold-comps")
def live_sold_comps_cmd(
    sport: str = typer.Option(
        ...,
        help="NFL, NBA, MLB or AFL",
    ),
    title: str = typer.Option(
        ...,
        help="Exact target card listing title",
    ),
    limit: int = typer.Option(
        100,
        help="Maximum ephemeral API rows per query",
    ),
):
    """
    Query recent confirmed eBay sold comps through The Card API.

    Free-tier API transaction rows are never written to SQLite,
    JSON, CSV or disk cache.
    """
    sport = sport.upper()

    identity = parse_identity(title, sport)

    provider = TheCardApiSoldCompProvider()

    missing = provider.missing_credentials()

    if missing:
        console.print(
            "[red]Missing THE_CARD_API_KEY in local .env.[/red]"
        )
        raise typer.Exit(1)

    engine = EphemeralSoldCompEngine(
        provider=provider,
        results_per_query=limit,
    )

    result = engine.scan_identity(
        source_listing_external_id="EPHEMERAL-LIVE",
        sport=sport,
        identity=identity,
    )

    console.print("")
    console.print(
        "[bold]THE CARD API - EPHEMERAL SOLD COMP AUDIT[/bold]"
    )
    console.print(
        "PERSISTENCE_ALLOWED=NO"
    )
    console.print(
        f"IDENTITY_QUALITY={result.identity_quality:.3f}"
    )
    console.print(
        f"QUERIES={result.query_count}"
    )
    console.print(
        f"FETCHED_RECENT={result.fetched_count}"
    )
    console.print(
        f"ACCEPTED={result.accepted_count}"
    )
    console.print(
        f"EXACT={result.exact_count}"
    )
    console.print(
        f"STRONG={result.strong_count}"
    )
    console.print(
        f"REJECTED={result.rejected_count}"
    )
    console.print(
        f"VALUATION_STATUS={result.valuation.status}"
    )

    if result.valuation.fair_value_aud is not None:
        console.print(
            f"FAIR_VALUE_AUD=A${result.valuation.fair_value_aud:.2f}"
        )
        console.print(
            f"COMP_CONFIDENCE={result.valuation.comp_confidence:.3f}"
        )
    else:
        console.print("FAIR_VALUE_AUD=UNAVAILABLE")

    table = Table(
        title="Accepted Confirmed Recent Sold Comps"
    )

    for column in [
        "DATE",
        "LEVEL",
        "PRICE",
        "AUD_VALUE",
        "TYPE",
        "TITLE",
    ]:
        table.add_column(column)

    for comp, match in result.comp_matches:
        raw_price = (
            f"{comp.currency} {comp.sold_price:.2f}"
        )
        aud = (
            f"A${comp.sold_price_aud:.2f}"
            if comp.sold_price_aud is not None
            else "FX_REQUIRED"
        )

        table.add_row(
            comp.sold_date,
            match.match_level.value,
            raw_price,
            aud,
            comp.sale_type or "",
            comp.title[:90],
        )

    console.print(table)

    if any(
        comp.sold_price_aud is None
        for comp, _ in result.comp_matches
    ):
        console.print(
            "[yellow]Foreign-currency comps were NOT converted "
            "using an invented FX rate and therefore cannot drive "
            "AUD valuation yet.[/yellow]"
        )

    console.print(
        "[yellow]Raw API sales were held in memory only and "
        "were not persisted.[/yellow]"
    )


if __name__ == "__main__":
    app()
