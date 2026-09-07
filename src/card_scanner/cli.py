from __future__ import annotations
import typer
from rich.console import Console
from rich.table import Table

from .db import finish_scan_run, init_db, start_scan_run, upsert_listing, save_valuation
from .identity import parse_identity
from .market_engine import MarketEngine
from .models import Listing
from .scoring import score_listing
from .sold_comps import import_sold_comp_csv
from .sources.ebay import EbaySource
from .sources.cherry import CherrySource

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
    imported, matches = import_sold_comp_csv(csv_path, sport.upper())
    console.print(
        f"[green]Imported {imported} sold comps and saved {matches} comparable matches.[/green]"
    )

if __name__ == "__main__":
    app()
