# CARD SCANNER ROADMAP

## Phase 1 — ingestion foundation
- [x] NFL
- [x] NBA
- [x] MLB
- [x] AFL
- [x] eBay Browse API adapter
- [x] Cherry Collectables adapter
- [x] SQLite listing history
- [x] Basic identity parser
- [x] Opportunity scoring skeleton

## Phase 2 — exact card identity
- Checklist databases by set/year/sport
- Player dictionaries
- Card number extraction
- Parallel taxonomy
- Serial-number hierarchy
- Grader/grade normalization
- Image-assisted confirmation

## Phase 3 — sold comps
- Exact sold-card matching
- Raw / PSA 9 / PSA 10 separation
- Currency conversion to AUD
- Recency weighting
- Auction vs BIN handling
- Outlier rejection
- Comp confidence model

## Phase 4 — opportunity engine
- Landed cost
- GST / international shipping
- Quick-sale value
- Fair retail value
- Grading EV
- Liquidity / sales velocity
- Seller / listing risk
- "WHY IS IT CHEAP?" disproof checks

## Phase 5 — discovery + alerts
- [x] Newly listed detector
- [x] Price-change detector
- Misspelling / under-described listing detector
- Cherry new-arrival monitor
- High-score alerts
- Watchlist / player trajectory layer
- Dashboard

## Rule
No auto-buying until the scanner has been audited on historical and live opportunities.

## UNDER-DESCRIBED LISTING INTELLIGENCE V1 COMPLETE

Status: COMPLETE / VALIDATED / READY TO COMMIT

Delivered:

- dedicated under-description/title-quality assessment;
- CLEAR / REVIEW / POOR_IDENTITY / NOT_APPLICABLE classification;
- structural identity anomaly signals;
- sealed/box/pack/repack exclusion from individual-card scoring;
- opportunity scanner integration;
- explainable mispricing integration;
- CLI title-identity status and risk output;
- conservative parser precision fixes discovered during live validation;
- regression coverage for detector governance and parser behavior;
- live four-store bounded validation.

Final live validation:

- 181 listings observed;
- 165 applicable individual-card listings;
- 160 CLEAR;
- 5 REVIEW;
- 0 POOR_IDENTITY;
- 16 NOT_APPLICABLE;
- 3.03% applicable review rate;
- zero sold API calls;
- zero persistence;
- zero history writes.

Governance remains locked:

- no BUY or STRONG_BUY from title-quality evidence alone;
- minimum sold-comp identity quality remains 0.70;
- active asks do not establish fair value;
- no hidden-attribute inference;
- no matching relaxation;
- no generic Black to Panini Black inference;
- no abbreviated-season inference yet.

Deferred future work:

- governed abbreviated-season normalization such as 10-11 to canonical season only after ambiguity rules are designed and tested;
- independent metadata/image evidence for true omitted-attribute detection;
- broader product alias expansion only when supported by live false-positive evidence;
- continued precision monitoring as additional stores and sports-card inventories are added.

## Completed — Sold Query Budget Efficiency V1

- Shared sold-query budgets now permit a final one-query candidate instead of requiring two calls to remain before every candidate.
- EphemeralSoldCompEngine accepts a bounded per-candidate query allowance of zero to two calls.
- Supplemental sold search is suppressed when the candidate allowance is exhausted.
- Existing strict sold identity matching and valuation thresholds are unchanged.
- Added regression coverage for one-query scans, supplemental-query suppression, odd shared budgets, and valuation from three exact comps returned by a single query.
