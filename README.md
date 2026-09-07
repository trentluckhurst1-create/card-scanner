# CARD SCANNER V1

Automated sports-card mispricing scanner for NFL, NBA, MLB and AFL cards.

The goal is not to find cheap listings. The goal is to compare a Cherry Collectables listing against defensible market evidence with enough identity confidence to justify conservative statuses such as `ACTIVE_MARKET_CHEAP`, `WATCH`-style review, or `PASS`-style rejection later. `BUY` is intentionally disabled unless genuine sold transaction evidence exists.

## Architecture

Core flow:

1. Ingest live Cherry Collectables singles through the Shopify JSON collection endpoints.
2. Parse exact card identity: sport, year, brand/set, player, card number, parallel, serial denominator, rookie/1st, autograph, memorabilia, grader and grade.
3. Build exact and broad comparable queries from the normalized identity.
4. Search current marketplace listings with the official eBay Browse API.
5. Parse every marketplace result with the same identity engine.
6. Classify each marketplace result as `EXACT`, `STRONG`, `RELATED` or `REJECT`, with reasons.
7. Store active market listings, snapshots, matches, rejected evidence and metrics separately from Cherry listings.
8. Import legitimate manual sold comps separately when available.

Active listings and sold comps are separate data paths. Active asks can show whether Cherry appears cheap against current asking inventory, but they are not fair value.

## Setup

```powershell
cd "C:\Users\trent\OneDrive\CARD SCANNER\card_scanner_v1"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m card_scanner.cli init-db
python -m unittest discover -s tests -v
```

## eBay Credentials

The live market adapter uses the official eBay Browse API:

`https://api.ebay.com/buy/browse/v1/item_summary/search`

OAuth application tokens are requested from:

`https://api.ebay.com/identity/v1/oauth2/token`

Add these values to `.env`:

```powershell
EBAY_CLIENT_ID=
EBAY_CLIENT_SECRET=
EBAY_MARKETPLACE_ID=EBAY_AU
```

Secrets must stay out of source control. `.env.example` contains blank placeholders only.

## Commands

Initialize or migrate the SQLite schema:

```powershell
python -m card_scanner.cli init-db
```

Refresh Cherry listings:

```powershell
python -m card_scanner.cli scan-cherry --sport MLB --limit 20
```

Scan Cherry against live eBay active listings:

```powershell
python -m card_scanner.cli scan-market --source cherry --sport MLB --limit 20
python -m card_scanner.cli scan-market --source cherry --sport ALL --limit 20
```

If eBay credentials are missing, `scan-market` fails safely and prints the missing variable names without exposing secrets.

Import manual sold comps from a permitted source:

```powershell
python -m card_scanner.cli import-sold-comps --csv .\manual_sold_comps.csv --sport MLB
```

CSV fields:

```text
source,sale_id,sold_date,title,sold_price,currency,shipping,sold_price_aud,URL,notes
```

If a sold comp is already in AUD, the importer can calculate AUD exactly. If it is in a foreign currency and `sold_price_aud` is blank, the AUD value remains unknown rather than using a guessed exchange rate.

## Active Market Metrics

`active_lowest_aud`, `active_median_aud`, `active_trimmed_median_aud`, `active_mean_aud`, `active_max_aud` and discount percentages are based only on accepted active marketplace matches with AUD landed prices.

Foreign-currency listings are marked `FX_PENDING` and excluded from AUD metrics until a real FX provider is configured.

Active asking prices are not sold prices. Do not treat `active_market_median` or any active asking metric as fair value.

## Sold Comps

The code includes a `SoldCompProvider` interface and a manual CSV import path. No automated 130 Point provider exists, and the project must not scrape 130 Point or undocumented/private endpoints.

Future permitted sold-comp providers can feed normalized sale records into the same matching and valuation architecture.

## Risk Flags

Marketplace titles are scanned for explainable risk flags, including digital, custom, reprint, facsimile, reproduction, replica, lot, bundle, box, pack, damage, creases, scratches, print lines, altered, trimmed, authentic-only, expired redemption, redemption, missing autograph and unknown variation.

Some flags reject a listing as a comparable immediately. Others are stored for later risk penalties.

## Limits

Current value status is conservative:

- `INSUFFICIENT_IDENTITY`
- `NO_MARKET_MATCHES`
- `ACTIVE_MARKET_CHEAP`
- `ACTIVE_MARKET_NORMAL`
- `ACTIVE_MARKET_EXPENSIVE`

`BUY` is disabled without genuine sold comps that pass confidence gates. `fair_value_aud` and `quick_sale_value_aud` must remain null or explicitly unavailable when only active asking prices exist.

## Governance

Market search uses per-run query caching and conservative defaults:

```powershell
MARKET_CACHE_HOURS=6
MAX_MARKET_QUERIES_PER_RUN=25
EBAY_RESULTS_PER_QUERY=25
```

Exact-card queries omit serial numerator but keep serial denominator, parallel, grade and other material identity fields. This allows `Gold Wave 38/50` and `Gold Wave 7/50` to compare, while preventing `/50` from being treated as `/250`, base, raw-vs-graded, auto-vs-non-auto, or a different parallel.

## Tests

```powershell
$env:PYTHONPATH='src'
python -m compileall src tests
python -m unittest discover -s tests -v
```

The deterministic suite covers identity parsing, suffix normalization, prefix cleanup, exact matching, rejection rules, schema migration and mocked eBay token/query caching.

## Next Steps

Add a permitted real FX provider, then add a permitted sold-comp provider or continue importing manual sales. Only after genuine sold transactions are available should the valuation layer produce fair value, quick-sale value and any BUY-style decision.
