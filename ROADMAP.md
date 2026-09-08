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
