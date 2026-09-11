# Free Marketplace Expansion — Stage 7

## Live now as external research links

Exact-card groups expose identity-aware searches to:

- eBay Australia — live marketplace inventory search.
- 130 Point — free cross-marketplace live/sold research covering eBay, Fanatics Collect, Goldin, MySlabs, Pristine Auctions, Heritage and others.
- SportsCardsPro — external card pricing research.

External sites are research evidence only. Their proprietary data is not scraped, cached or republished by this public app unless an authorized API/data agreement permits it.

## eBay native integration target

Use eBay Browse API for active listings once application credentials are available. eBay documents a default 5,000 calls/day for Browse API and requires an application access token via client-credentials OAuth. Australia is supported. Marketplace Insights (historical/sold insight) is restricted and is not open to new users, so do not design sold-value governance around obtaining it.

Planned native eBay active-listing fields:
- item id
- title
- image
- item URL
- current price/currency
- shipping/delivery where available
- condition
- buying option
- seller/location metadata where permitted

All eBay results must pass Card Scanner canonical identity matching before joining an EXACT_CARD group. Related variants stay separate.

## Governance

- Active marketplace asks are not fair value.
- External research links cannot create BUY or STRONG_BUY.
- No third-party proprietary price/history dataset is copied into the public feed without authorization.
- Genuine sold evidence remains subject to the existing sold-comp gate.
