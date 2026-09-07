from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src"),
)

from card_scanner.fx import RbaFxProvider
from card_scanner.the_card_api import TheCardApiSoldCompProvider


RBA_FIXTURE = """Title,A$1=USD,A$1=EUR,A$1=GBP,A$1=JPY,A$1=NZD,A$1=CAD
Description,USD,EUR,GBP,JPY,NZD,CAD
Frequency,Daily,Daily,Daily,Daily,Daily,Daily
Type,Indicative,Indicative,Indicative,Indicative,Indicative,Indicative
Units,USD,EUR,GBP,JPY,NZD,CAD
Source,WM/Reuters,RBA,RBA,RBA,RBA,RBA
Publication date,08-Sep-2026,08-Sep-2026,08-Sep-2026,08-Sep-2026,08-Sep-2026,08-Sep-2026
Series ID,FXRUSD,FXREUR,FXRUKPS,FXRJY,FXRNZD,FXRCD
04-Sep-2026,0.7210,0.6201,0.5327,112.71,1.2227,0.9943
07-Sep-2026,0.7209,0.6207,0.5332,112.32,1.2264,0.9971
"""


class FakeResponse:
    def __init__(self, text="", payload=None):
        self.text = text
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeRbaClient:
    def __init__(self):
        self.calls = []

    def get(self, url, params=None, headers=None):
        self.calls.append(url)
        return FakeResponse(text=RBA_FIXTURE)


class FakeCardApiClient:
    def __init__(self, payload):
        self.payload = payload

    def get(self, url, params=None, headers=None):
        return FakeResponse(payload=self.payload)


class RbaFxTests(unittest.TestCase):
    def test_usd_conversion_direction_is_foreign_per_aud(self):
        provider = RbaFxProvider(
            client=FakeRbaClient(),
        )

        result = provider.convert_to_aud(
            100.0,
            "USD",
            "2026-09-07",
        )

        self.assertEqual(result.status, "CONVERTED")
        self.assertEqual(result.rate_date, "2026-09-07")
        self.assertEqual(result.foreign_per_aud, 0.7209)
        self.assertEqual(result.aud_amount, 138.72)

    def test_weekend_uses_latest_prior_rate_never_future(self):
        provider = RbaFxProvider(
            client=FakeRbaClient(),
        )

        result = provider.convert_to_aud(
            100.0,
            "USD",
            "2026-09-06",
        )

        self.assertEqual(result.status, "CONVERTED")
        self.assertEqual(result.rate_date, "2026-09-04")
        self.assertEqual(result.foreign_per_aud, 0.7210)
        self.assertEqual(result.aud_amount, 138.70)

    def test_supported_currency_series_parse(self):
        provider = RbaFxProvider(
            client=FakeRbaClient(),
        )

        expected = {
            "USD": 0.7209,
            "EUR": 0.6207,
            "GBP": 0.5332,
            "JPY": 112.32,
            "NZD": 1.2264,
            "CAD": 0.9971,
        }

        for currency, rate in expected.items():
            result = provider.convert_to_aud(
                100.0,
                currency,
                "2026-09-07",
            )

            self.assertEqual(result.status, "CONVERTED")
            self.assertEqual(result.foreign_per_aud, rate)
            self.assertIsNotNone(result.aud_amount)

    def test_unsupported_currency_is_not_guessed(self):
        provider = RbaFxProvider(
            client=FakeRbaClient(),
        )

        result = provider.convert_to_aud(
            100.0,
            "CHF",
            "2026-09-07",
        )

        self.assertEqual(
            result.status,
            "UNSUPPORTED_CURRENCY",
        )
        self.assertIsNone(result.aud_amount)

    def test_csv_download_is_session_cached(self):
        client = FakeRbaClient()

        provider = RbaFxProvider(
            client=client,
        )

        provider.convert_to_aud(
            100,
            "USD",
            "2026-09-07",
        )

        provider.convert_to_aud(
            100,
            "EUR",
            "2026-09-07",
        )

        self.assertEqual(len(client.calls), 1)
        self.assertEqual(provider.query_count, 1)

    def test_card_api_foreign_sale_can_receive_fx_in_memory(self):
        payload = {
            "data": [
                {
                    "id": "USD1",
                    "platform": "ebay",
                    "price_confirmed": True,
                    "title": (
                        "2020 Panini Prizm PATRICK MAHOMES "
                        "Lazer Prizm PSA 10"
                    ),
                    "sale_date": "2026-09-06",
                    "price": 100.0,
                    "currency": "USD",
                }
            ]
        }

        fx = RbaFxProvider(
            client=FakeRbaClient(),
        )

        provider = TheCardApiSoldCompProvider(
            api_key="tca_test",
            client=FakeCardApiClient(payload),
            fx_provider=fx,
        )

        comp = provider.sold_comps(
            "NFL",
            "Patrick Mahomes",
            50,
        )[0]

        self.assertEqual(comp.currency, "USD")
        self.assertEqual(comp.sold_price, 100.0)
        self.assertEqual(comp.sold_price_aud, 138.70)
        self.assertIn(
            "FX_SOURCE=rba_f11_1",
            comp.notes,
        )
        self.assertIn(
            "FX_RATE_DATE=2026-09-04",
            comp.notes,
        )


if __name__ == "__main__":
    unittest.main()
