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

Run acquisition-store opportunity scans:

```powershell
python -m card_scanner.cli scan-opportunities --source cherry --sport AFL --listings-per-sport 5 --max-candidates 2 --max-sold-queries 2
python -m card_scanner.cli scan-opportunities --source sportscardstore --sport AFL --listings-per-sport 5 --max-candidates 2 --max-sold-queries 2
python -m card_scanner.cli scan-opportunities --source gimko --sport AFL --listings-per-sport 5 --max-candidates 1 --max-sold-queries 2
python -m card_scanner.cli scan-opportunities --source all --sport AFL --listings-per-sport 5 --max-candidates 2 --max-sold-queries 2
python -m card_scanner.cli scan-opportunities --source all --sport NBA --listings-per-sport 25 --max-candidates 10 --sold-limit 100 --max-sold-queries 10
```

Gimko V1 supports AFL Buy Out/fixed-price listings only. It uses the public category HTML, does not persist HTML, and treats full team/base/complete set listings as multi-card set risk rather than single-card opportunities.

Acquisition-store scans can read from Cherry, Sports Card Store, Gimko and Urban Empire. `--source all` pools the supported stores for the selected sport, while each candidate's cross-store reference pool excludes the candidate's own source.

Run governed paginated Cherry ingestion:

```powershell
python -m card_scanner.cli scan-cherry-all --sport MLB --max-products 20 --page-size 20 --force
python -m card_scanner.cli scan-cherry-all --sport ALL
```

The full collector records scan run IDs, first/last seen state, current and previous prices, snapshots, `NEW_LISTING`, `PRICE_DROP`, `PRICE_RISE`, `RELISTED`, `MISSING_FROM_SCAN` and `INACTIVE` events. A listing is not marked inactive until it has been missed for `CHERRY_MISSING_SCAN_THRESHOLD` scans.

Audit identity coverage:

```powershell
python -m card_scanner.cli audit-identities --source cherry --sport ALL
python -m card_scanner.cli identity-failures --sport AFL --limit 20
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
python -m card_scanner.cli audit-sold-comps --limit 50
python -m card_scanner.cli value-sold-comps --sport MLB
```

CSV fields:

```text
source,sale_id,sold_date,title,sold_price,currency,shipping,sold_price_aud,URL,notes
```

If a sold comp is already in AUD, the importer can calculate AUD exactly. If it is in a foreign currency and `sold_price_aud` is blank, the AUD value remains unknown rather than using a guessed exchange rate.

Report opportunities and events:

```powershell
python -m card_scanner.cli opportunities --sport MLB --limit 50 --export-csv output/mlb_opportunities.csv
python -m card_scanner.cli new-cherry-listings --sport ALL --limit 50
python -m card_scanner.cli price-drops --sport ALL --limit 50
python -m card_scanner.cli insufficient-comps --sport ALL --limit 50
```

Watchlist:

```powershell
python -m card_scanner.cli watch-add --watch-type player --value "Kyson Witherspoon" --sport MLB
python -m card_scanner.cli watch-list
python -m card_scanner.cli watch-history --limit 50
python -m card_scanner.cli watch-remove --watch-id 1
```

## Active Market Metrics

`active_lowest_aud`, `active_median_aud`, `active_trimmed_median_aud`, `active_mean_aud`, `active_max_aud` and discount percentages are based only on accepted active marketplace matches with AUD landed prices.

Foreign-currency listings are marked `FX_PENDING` and excluded from AUD metrics until a real FX provider is configured.

Active asking prices are not sold prices. Do not treat `active_market_median` or any active asking metric as fair value.

Cross-store active listings are reference-only. They can support `WATCH`-style context or explain why a candidate lacks comparable asking inventory, but they must never produce `BUY`, `STRONG_BUY`, `fair_value_aud` or `quick_sale_value_aud`.

Cross-store diagnostics include a reporting-only cumulative identity funnel: `CROSS_STORE`, `IDENTITY_PRESENT`, `SAME_PLAYER`, `SAME_YEAR`, `SAME_PRODUCT`, `SAME_CARD_NUMBER`, `SAME_PARALLEL`, `SAME_SERIAL`, `SAME_ROOKIE`, `SAME_AUTO_MEM`, `SAME_GRADING` and `EXACT_STRONG`. The funnel explains where possible references fail; it does not create or loosen accepted references.

## Active Listing History

The acquisition-store scanner can persist lawful active-listing history for Cherry, Sports Card Store Australia, Gimko and Urban Empire. scan-opportunities records this history by default; use --no-record-history to disable it.

History is keyed by source + external_id and tracks first seen, last seen, current/previous/minimum/maximum asking price, observation count, price-change counts and conservative lifecycle context.

Bounded or partial scans do not infer that an unseen listing disappeared or became inactive. A listing can only be treated as relisted when prior state explicitly records it as inactive.

Active listing history is timing and risk context only. It cannot create air_value_aud, quick_sale_value_aud, satisfy the minimum sold-comp requirement, or create BUY / STRONG_BUY. A price drop is evidence about the seller's asking-price movement, not proof of card value.

The Card API sold-sale data remains on a separate ephemeral path. Raw API responses, normalized API sales and API sold matches are not written into active listing history or persisted by the live opportunity scanner.
## Mispricing Assessment

The scanner ranks opportunities by explainable mispricing quality, not raw discount alone. The `MISPRICE` score combines sold fair-value edge, identity confidence, sold-comp confidence, exact-comp depth, liquidity, comp recency, price dispersion, risk flags and cross-store ask context.

Each scan row reports `LOOKS_CHEAP` and `MAY_BE_CHEAP`. `LOOKS_CHEAP` captures evidence such as sold fair-value edge, landed cost below quick-sale value and cross-store active ask discount. `MAY_BE_CHEAP` captures legitimate explanations such as insufficient sold evidence, weak identity confidence, low liquidity, wide sold-price dispersion, old comps, falling market direction, title risk language or weak cross-store overlap.

Raw percentage edge is intentionally capped by evidence quality. A smaller edge with exact identity, recent exact sold comps and low dispersion should outrank a larger discount with weak sold evidence or unresolved risk.

## Sold Comps

The code includes a `SoldCompProvider` interface, a manual CSV import path and an ephemeral The Card API evaluation provider. No automated 130 Point provider exists, and the project must not scrape 130 Point, eBay sold pages or undocumented/private endpoints.

The Card API sales are held in memory only during the scan. Raw API responses, normalized API sales and API sold matches are not persisted to SQLite, JSON, CSV or disk cache. Free-tier use is evaluation / personal / non-commercial only.

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
CHERRY_PAGE_SIZE=250
CHERRY_MAX_PRODUCTS_PER_SPORT=5000
CHERRY_SCAN_CACHE_MINUTES=30
CHERRY_MISSING_SCAN_THRESHOLD=3
EXACT_COMP_MAX_AGE_DAYS=365
RELATED_COMP_MAX_AGE_DAYS=180
MIN_EXACT_COMPS_HIGH_CONFIDENCE=3
MIN_TOTAL_COMPS_MEDIUM_CONFIDENCE=3
OUTLIER_IQR_MULTIPLIER=1.5
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

## UNDER-DESCRIBED LISTING INTELLIGENCE V1

The scanner includes a precision-first title-quality and identity-anomaly layer for active marketplace listings.

Its purpose is not to invent hidden card attributes. All current acquisition sources derive card identity from the same public seller title, so the system cannot legitimately claim that an attribute was omitted unless independent evidence exists.

V1 therefore asks a narrower and defensible question:

Is the seller title sufficiently specific and internally coherent for reliable individual-card identification?

Possible outcomes:

- CLEAR - no material title-identity anomaly detected.
- REVIEW - identity is usable but contains unresolved ambiguity or missing structural information.
- POOR_IDENTITY - title identity is materially inadequate for dependable card identification.
- NOT_APPLICABLE - sealed boxes, packs, bundles, repacks, or other non-individual-card products.

The detector may flag structural issues such as missing year, missing recognized product family, weak identity attached to serial numbering, weak identity attached to card numbering, generic player identity, or extremely incomplete core identity.

Important governance:

- Under-description intelligence cannot create BUY or STRONG_BUY.
- It cannot satisfy or relax the sold-comparable threshold.
- It cannot relax card matching requirements.
- It cannot infer unseen rookie, autograph, memorabilia, serial, grading, parallel, or other attributes.
- Active listing titles remain marketplace evidence only; they do not establish fair value.
- comp_quality remains sold-comp identity completeness and is not treated as a generic title-quality threshold.
- The live sold-comp identity threshold remains 0.70.
- Sealed and repack products are excluded from individual-card title-risk scoring.

Parser precision work introduced with this tranche includes:

- prevention of serial/card-number fragments such as Gold /10 from being promoted to player identity;
- narrow AFL product recognition for AFL Supremacy, AFL Optimum, AFL Eminence, and AFL Legacy;
- narrow four-digit-year Illusions shorthand normalization to Panini Illusions;
- explicit Chronology product recognition;
- Letterman treated as a card descriptor rather than part of a player name;
- deliberate refusal to infer generic Black as Panini Black, because Black is also a legitimate parallel descriptor;
- deliberate refusal to infer abbreviated seasons such as 10-11 until abbreviated-season normalization has its own governed design.

Live four-store validation was performed across NFL, NBA, MLB, and AFL using Cherry, Sports Card Store Australia, Gimko, and Urban Empire, with no sold API calls, no history writes, and no persistence.

Final bounded validation:

- total listings: 181
- applicable individual-card listings: 165
- CLEAR: 160
- REVIEW: 5
- POOR_IDENTITY: 0
- NOT_APPLICABLE: 16
- applicable review rate: 3.03%

The five retained REVIEW cases were intentionally left unresolved because certainty would require unsafe inference: one ambiguous Black NFL product title, one abbreviated 10-11 NBA season title, and three yearless Chronology listings.

Under-description assessment is exposed in opportunity results and CLI reporting as title-identity status/risk. Mispricing assessment may apply a confidence penalty for REVIEW or POOR_IDENTITY, but the underlying opportunity status and valuation evidence gates remain unchanged.
