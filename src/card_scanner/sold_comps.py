from __future__ import annotations

import csv
from pathlib import Path

from .comp_key import comp_quality
from .currency import AudOnlyCurrencyProvider, CurrencyProvider
from .db import fetch_listings, save_sold_comp_match, upsert_sold_comp
from .identity import parse_identity
from .market_matching import assess_match
from .models import MatchLevel, SoldComp, SoldCompMatch


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    return float(text)


def import_sold_comp_csv(
    path: str | Path,
    sport: str,
    currency_provider: CurrencyProvider | None = None,
) -> tuple[int, int]:
    currency_provider = currency_provider or AudOnlyCurrencyProvider()
    imported = 0
    matches_saved = 0
    cherry_listings = fetch_listings("cherry", sport, 10000)

    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)

        for row in reader:
            source = (row.get("source") or "manual").strip()
            sale_id = (row.get("sale_id") or "").strip()
            title = (row.get("title") or "").strip()

            if not source or not sale_id or not title:
                raise ValueError("CSV rows require source, sale_id and title")

            sold_price = float(row.get("sold_price") or 0)
            currency = (row.get("currency") or "AUD").strip().upper()
            shipping = _float_or_none(row.get("shipping"))
            supplied_aud = _float_or_none(row.get("sold_price_aud"))

            if supplied_aud is not None:
                sold_price_aud = supplied_aud
            else:
                sold_price_aud, _ = currency_provider.to_aud(
                    sold_price + (shipping or 0.0),
                    currency,
                )

            comp = SoldComp(
                source=source,
                sale_id=sale_id,
                sold_date=(row.get("sold_date") or "").strip(),
                title=title,
                sold_price=sold_price,
                currency=currency,
                shipping=shipping,
                sold_price_aud=sold_price_aud,
                sale_type=(row.get("sale_type") or "").strip() or None,
                url=(row.get("URL") or row.get("url") or "").strip() or None,
                notes=(row.get("notes") or "").strip() or None,
                identity=parse_identity(title, sport),
            )
            upsert_sold_comp(comp)
            imported += 1

            for listing in cherry_listings:
                if not listing.identity or comp_quality(listing.identity) < 0.70:
                    continue

                assessment = assess_match(
                    listing.identity,
                    comp.identity,
                    [],
                )

                if assessment.match_level == MatchLevel.REJECT:
                    continue

                save_sold_comp_match(
                    SoldCompMatch(
                        source_listing_external_id=listing.external_id,
                        sold_source=comp.source,
                        sale_id=comp.sale_id,
                        match_level=assessment.match_level,
                        match_score=assessment.match_score,
                        match_reasons=assessment.match_reasons,
                        rejection_reasons=assessment.rejection_reasons,
                    )
                )
                matches_saved += 1

    return imported, matches_saved
