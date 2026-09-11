# Stage 7 Active Price Comparison Contract

The active price-comparison layer compares currently listed asking prices across supported stores. It is not a valuation engine.

## Comparison tiers

1. `EXACT_CARD` — listings share the same strict canonical card-family key. Cheapest-store and savings calculations can be treated as like-for-like active asking-price comparisons.
2. `SAME_PRODUCT_VARIANTS` — same sport, player, year and product family, but the card-family keys differ. These rows provide market context only; parallels, card numbers, serial runs or grading can differ.
3. `PLAYER_YEAR_MARKET` — same sport, player and year across stores after exact and same-product matches have been removed. This is the broadest active-market context and is never an exact-card comparison.

## Published fields

Each comparison group can include lowest, median and highest landed AUD asking prices, cheapest store, next-best store, spread, dollar savings and percentage savings, plus direct listing URLs.

## Governance

- Active asking prices are not fair value.
- Related variants are not exact equivalents.
- This layer cannot create BUY or STRONG_BUY decisions.
- Fair value remains locked behind the governed sold-comp valuation path.
- No raw sold-provider responses are written into this comparison layer.
