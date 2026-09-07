from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .comp_key import comp_quality
from .currency import AudOnlyCurrencyProvider, CurrencyProvider
from .db import (
    fetch_listings,
    save_sold_comp_match,
    sold_comp_exists,
    upsert_sold_comp,
)
from .identity import parse_identity
from .market_matching import assess_match
from .models import MatchLevel, SoldComp, SoldCompMatch


REQUIRED_FIELDS = {
    "source",
    "sale_id",
    "sold_date",
    "title",
    "sold_price",
    "currency",
}


@dataclass
class SoldCompImportResult:
    imported: int = 0
    stored_without_aud: int = 0
    duplicates_in_file: int = 0
    duplicates_existing: int = 0
    malformed_rows: int = 0
    invalid_dates: int = 0
    invalid_prices: int = 0
    missing_currency: int = 0
    missing_aud_conversion: int = 0
    matches_saved: int = 0
    errors: list[str] = field(default_factory=list)


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    return float(text)


def _valid_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False

    return True


def import_sold_comp_csv(
    path: str | Path,
    sport: str,
    currency_provider: CurrencyProvider | None = None,
) -> SoldCompImportResult:
    currency_provider = currency_provider or AudOnlyCurrencyProvider()
    result = SoldCompImportResult()
    seen_sale_keys: set[tuple[str, str]] = set()
    cherry_listings = fetch_listings("cherry", sport, 10000)

    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing_fields = REQUIRED_FIELDS.difference(fields)

        if missing_fields:
            raise ValueError(
                "CSV missing required fields: "
                + ", ".join(sorted(missing_fields))
            )

        for line_number, row in enumerate(reader, start=2):
            source = (row.get("source") or "manual").strip()
            sale_id = (row.get("sale_id") or "").strip()
            sold_date = (row.get("sold_date") or "").strip()
            title = (row.get("title") or "").strip()
            currency = (row.get("currency") or "").strip().upper()

            if not source or not sale_id or not title:
                result.malformed_rows += 1
                result.errors.append(f"line {line_number}: source, sale_id and title are required")
                continue

            sale_key = (source, sale_id)
            if sale_key in seen_sale_keys:
                result.duplicates_in_file += 1
                result.errors.append(f"line {line_number}: duplicate sale ID in file {source}/{sale_id}")
                continue

            seen_sale_keys.add(sale_key)

            if sold_comp_exists(source, sale_id):
                result.duplicates_existing += 1

            if not sold_date or not _valid_date(sold_date):
                result.invalid_dates += 1
                result.errors.append(f"line {line_number}: invalid sold_date {sold_date!r}; expected YYYY-MM-DD")
                continue

            try:
                sold_price = float(row.get("sold_price") or "")
            except ValueError:
                result.invalid_prices += 1
                result.errors.append(f"line {line_number}: invalid sold_price")
                continue

            if sold_price <= 0:
                result.invalid_prices += 1
                result.errors.append(f"line {line_number}: sold_price must be positive")
                continue

            if not currency:
                result.missing_currency += 1
                result.errors.append(f"line {line_number}: missing currency")
                continue

            try:
                shipping = _float_or_none(row.get("shipping"))
                supplied_aud = _float_or_none(row.get("sold_price_aud"))
            except ValueError:
                result.invalid_prices += 1
                result.errors.append(f"line {line_number}: invalid shipping or sold_price_aud")
                continue

            if supplied_aud is not None:
                sold_price_aud = supplied_aud
            else:
                sold_price_aud, _ = currency_provider.to_aud(
                    sold_price + (shipping or 0.0),
                    currency,
                )

            if sold_price_aud is None:
                result.missing_aud_conversion += 1
                result.stored_without_aud += 1

            comp = SoldComp(
                source=source,
                sale_id=sale_id,
                sold_date=sold_date,
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
            result.imported += 1

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
                result.matches_saved += 1

    return result
