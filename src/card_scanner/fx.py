from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from io import StringIO
from typing import Any

import httpx

from .config import settings


RBA_SERIES_BY_CURRENCY = {
    "USD": "FXRUSD",
    "EUR": "FXREUR",
    "GBP": "FXRUKPS",
    "JPY": "FXRJY",
    "NZD": "FXRNZD",
    "CAD": "FXRCD",
}


@dataclass(frozen=True)
class FxConversion:
    original_amount: float
    original_currency: str
    aud_amount: float | None
    rate_date: str | None
    foreign_per_aud: float | None
    source: str
    status: str


def _parse_rba_date(value: str) -> date | None:
    text = str(value or "").strip()

    if not text:
        return None

    formats = (
        "%d-%b-%Y",
        "%Y-%m-%d",
        "%d/%m/%Y",
    )

    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    return None


class RbaFxProvider:
    """
    Historical FX conversion using RBA Statistical Table F11.1.

    RBA F11.1 rates are quoted as units of foreign currency per A$1.

    Therefore:

        AUD amount = foreign currency amount / RBA rate

    Weekend / holiday handling:
    use the latest published rate on or before the transaction date.
    Never use a future rate.

    The dataset is fetched once per provider session and held in memory.
    """

    name = "rba_f11_1"

    def __init__(
        self,
        csv_url: str | None = None,
        client: httpx.Client | Any | None = None,
    ):
        self.csv_url = csv_url or settings.rba_fx_csv_url
        self.client = client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "CARD-SCANNER/1.0",
                "Accept": "text/csv,*/*",
            },
        )

        self._rates: dict[date, dict[str, float]] | None = None
        self.query_count = 0

    @staticmethod
    def _parse_csv(text: str) -> dict[date, dict[str, float]]:
        rows = list(csv.reader(StringIO(text)))

        if not rows:
            raise RuntimeError("RBA FX CSV was empty.")

        series_row_index = None
        series_columns: dict[int, str] = {}

        for index, row in enumerate(rows):
            if not row:
                continue

            first = str(row[0] or "").strip().lower()

            if first == "series id":
                series_row_index = index

                for col_index, raw_series in enumerate(row[1:], start=1):
                    series_id = str(raw_series or "").strip()

                    for currency, expected_series in RBA_SERIES_BY_CURRENCY.items():
                        if series_id == expected_series:
                            series_columns[col_index] = currency
                            break

                break

        if series_row_index is None:
            raise RuntimeError(
                "RBA FX CSV did not contain a 'Series ID' metadata row."
            )

        if not series_columns:
            raise RuntimeError(
                "RBA FX CSV did not contain any supported FX series."
            )

        rates: dict[date, dict[str, float]] = {}

        for row in rows[series_row_index + 1:]:
            if not row:
                continue

            row_date = _parse_rba_date(row[0])

            if row_date is None:
                continue

            day_rates: dict[str, float] = {}

            for col_index, currency in series_columns.items():
                if col_index >= len(row):
                    continue

                raw_value = str(row[col_index] or "").strip()

                if not raw_value or raw_value.upper() in {
                    "NA",
                    "N/A",
                    "-",
                }:
                    continue

                try:
                    rate = float(raw_value.replace(",", ""))
                except ValueError:
                    continue

                if rate > 0:
                    day_rates[currency] = rate

            if day_rates:
                rates[row_date] = day_rates

        if not rates:
            raise RuntimeError(
                "RBA FX CSV contained no usable dated FX observations."
            )

        return rates

    def _load(self) -> dict[date, dict[str, float]]:
        if self._rates is not None:
            return self._rates

        self.query_count += 1

        response = self.client.get(self.csv_url)
        response.raise_for_status()

        self._rates = self._parse_csv(response.text)

        return self._rates

    def convert_to_aud(
        self,
        amount: float,
        currency: str,
        transaction_date: str | date,
    ) -> FxConversion:
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return FxConversion(
                original_amount=0.0,
                original_currency=str(currency or "").upper(),
                aud_amount=None,
                rate_date=None,
                foreign_per_aud=None,
                source=self.name,
                status="INVALID_AMOUNT",
            )

        normalized_currency = str(currency or "").strip().upper()

        if amount <= 0:
            return FxConversion(
                original_amount=amount,
                original_currency=normalized_currency,
                aud_amount=None,
                rate_date=None,
                foreign_per_aud=None,
                source=self.name,
                status="INVALID_AMOUNT",
            )

        if normalized_currency == "AUD":
            return FxConversion(
                original_amount=amount,
                original_currency="AUD",
                aud_amount=round(amount, 2),
                rate_date=(
                    transaction_date.isoformat()
                    if isinstance(transaction_date, date)
                    else str(transaction_date)
                ),
                foreign_per_aud=1.0,
                source="AUD_NATIVE",
                status="AUD_NATIVE",
            )

        if normalized_currency not in RBA_SERIES_BY_CURRENCY:
            return FxConversion(
                original_amount=amount,
                original_currency=normalized_currency,
                aud_amount=None,
                rate_date=None,
                foreign_per_aud=None,
                source=self.name,
                status="UNSUPPORTED_CURRENCY",
            )

        if isinstance(transaction_date, date):
            target_date = transaction_date
        else:
            try:
                target_date = date.fromisoformat(
                    str(transaction_date).strip()[:10]
                )
            except ValueError:
                return FxConversion(
                    original_amount=amount,
                    original_currency=normalized_currency,
                    aud_amount=None,
                    rate_date=None,
                    foreign_per_aud=None,
                    source=self.name,
                    status="INVALID_DATE",
                )

        rates = self._load()

        eligible_dates = [
            rate_date
            for rate_date, day_rates in rates.items()
            if (
                rate_date <= target_date
                and normalized_currency in day_rates
            )
        ]

        if not eligible_dates:
            return FxConversion(
                original_amount=amount,
                original_currency=normalized_currency,
                aud_amount=None,
                rate_date=None,
                foreign_per_aud=None,
                source=self.name,
                status="NO_PRIOR_RATE",
            )

        rate_date = max(eligible_dates)
        rate = rates[rate_date][normalized_currency]

        if rate <= 0:
            return FxConversion(
                original_amount=amount,
                original_currency=normalized_currency,
                aud_amount=None,
                rate_date=rate_date.isoformat(),
                foreign_per_aud=None,
                source=self.name,
                status="INVALID_RATE",
            )

        aud_amount = amount / rate

        return FxConversion(
            original_amount=amount,
            original_currency=normalized_currency,
            aud_amount=round(aud_amount, 2),
            rate_date=rate_date.isoformat(),
            foreign_per_aud=rate,
            source=self.name,
            status="CONVERTED",
        )
