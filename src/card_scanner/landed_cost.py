from __future__ import annotations

from dataclasses import dataclass

from .config import settings
from .currency import AudOnlyCurrencyProvider, CurrencyProvider
from .models import Listing, MarketListing


@dataclass(frozen=True)
class LandedCost:
    landed_cost_aud: float | None
    price_aud: float | None
    shipping_aud: float | None
    fx_status: str
    notes: list[str]


def _configured_cherry_shipping() -> float | None:
    value = str(settings.cherry_shipping_aud).strip()
    if not value:
        return None

    return float(value)


def cherry_landed_cost(listing: Listing) -> LandedCost:
    if listing.currency.upper() != "AUD":
        return LandedCost(
            landed_cost_aud=None,
            price_aud=None,
            shipping_aud=None,
            fx_status="FX_PENDING",
            notes=["Cherry listing currency is not AUD"],
        )

    shipping = _configured_cherry_shipping()
    notes = ["local pickup possible metadata only"]

    if shipping is None:
        shipping = listing.shipping if listing.shipping else 0.0
        notes.append("shipping not configured; using listing shipping only")

    landed = round(listing.price + shipping, 2)

    return LandedCost(
        landed_cost_aud=landed,
        price_aud=round(listing.price, 2),
        shipping_aud=round(shipping, 2),
        fx_status="CONVERTED",
        notes=notes,
    )


def market_landed_cost(
    listing: MarketListing,
    currency_provider: CurrencyProvider | None = None,
) -> LandedCost:
    currency_provider = currency_provider or AudOnlyCurrencyProvider()

    if listing.shipping is None:
        return LandedCost(
            landed_cost_aud=None,
            price_aud=None,
            shipping_aud=None,
            fx_status="SHIPPING_UNKNOWN",
            notes=["shipping unknown; landed cost not defensible"],
        )

    landed, fx_status = currency_provider.to_aud(
        listing.price + listing.shipping,
        listing.currency,
    )

    return LandedCost(
        landed_cost_aud=landed,
        price_aud=listing.price if listing.currency.upper() == "AUD" else None,
        shipping_aud=listing.shipping if listing.currency.upper() == "AUD" else None,
        fx_status=fx_status,
        notes=[] if landed is not None else ["FX conversion unavailable"],
    )
