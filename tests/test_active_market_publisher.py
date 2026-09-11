from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

from card_scanner.fx import FxConversion
from card_scanner.models import CardIdentity, Listing


def _module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "publish_active_market.py"
    spec = importlib.util.spec_from_file_location("publish_active_market_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _listing(
    source: str,
    external_id: str,
    price: float,
    *,
    parallel: str = "Silver",
    currency: str = "AUD",
    shipping: float = 0.0,
) -> Listing:
    return Listing(
        source=source,
        external_id=external_id,
        url=f"https://example.test/{external_id}",
        title=f"2025 Topps Chrome Test Player {parallel} #43",
        sport="NFL",
        price=price,
        currency=currency,
        shipping=shipping,
        identity=CardIdentity(
            sport="NFL",
            player="Test Player",
            year="2025",
            brand="Topps",
            set_name="Topps Chrome",
            card_number="43",
            parallel=parallel,
            rookie=True,
        ),
    )


class _Fx:
    def convert_to_aud(self, amount: float, currency: str, transaction_date: date) -> FxConversion:
        assert currency == "USD"
        assert transaction_date == date(2026, 9, 11)
        return FxConversion(
            original_amount=amount,
            original_currency="USD",
            aud_amount=round(amount * 1.5, 2),
            rate_date="2026-09-10",
            foreign_per_aud=2 / 3,
            source="test_fx",
            status="CONVERTED",
        )


def test_active_market_payload_is_comparison_only_and_finds_exact_price_gap():
    module = _module()
    payload = module.build_active_market_payload(
        [
            _listing("cherry", "a", 100.0),
            _listing("gimko", "b", 125.0),
        ],
        generated_at="2026-09-11T00:00:00+00:00",
        stores_considered=4,
        stores_searched=4,
    )

    assert payload["feed_type"] == "ACTIVE_MARKET_COMPARISON_ONLY"
    assert payload["display_currency"] == "AUD"
    assert payload["metrics"]["active_cards"] == 2
    assert payload["metrics"]["exact_matches"] == 1
    group = payload["active_price_comparisons"]["groups"][0]
    assert group["comparison_type"] == "EXACT_CARD"
    assert group["cheapest_store"] == "cherry"
    assert group["saving_vs_highest_aud"] == 25.0
    assert payload["governance"] == {
        "contains_sold_evidence": False,
        "contains_fair_value": False,
        "can_create_buy": False,
        "persistent_history_claimed": False,
        "foreign_prices_converted_to_aud": True,
    }

    serialized = repr(payload).casefold()
    assert "sold_evidence" not in serialized.replace("contains_sold_evidence", "")
    assert "fair_value_aud" not in serialized
    assert "valuation" not in serialized


def test_active_market_payload_converts_usd_to_aud_before_price_comparison():
    module = _module()
    payload = module.build_active_market_payload(
        [
            _listing("australian-store", "aud", 120.0),
            _listing("us-store", "usd", 70.0, currency="USD", shipping=10.0),
        ],
        generated_at="2026-09-11T00:00:00+00:00",
        fx_provider=_Fx(),
        rate_date=date(2026, 9, 11),
    )

    usd = next(card for card in payload["market_cards"] if card["external_id"] == "usd")
    assert usd["asking_price"] == 70.0
    assert usd["currency"] == "USD"
    assert usd["landed_aud"] == 120.0
    assert usd["fx_status"] == "CONVERTED"
    assert usd["fx_rate_date"] == "2026-09-10"
    assert payload["metrics"]["foreign_currency_cards"] == 1
    assert payload["metrics"]["fx_converted_cards"] == 1

    group = payload["active_price_comparisons"]["groups"][0]
    assert group["lowest_active_ask_aud"] == 120.0
    assert group["highest_active_ask_aud"] == 120.0
    assert group["spread_aud"] == 0.0


def test_active_market_payload_deduplicates_same_store_external_id():
    module = _module()
    payload = module.build_active_market_payload(
        [
            _listing("cherry", "a", 100.0),
            _listing("cherry", "a", 100.0),
        ],
        generated_at="2026-09-11T00:00:00+00:00",
    )
    assert payload["metrics"]["active_cards"] == 1
    assert len(payload["market_cards"]) == 1


def test_related_variants_remain_non_exact_in_active_feed():
    module = _module()
    payload = module.build_active_market_payload(
        [
            _listing("cherry", "a", 100.0, parallel="Silver"),
            _listing("gimko", "b", 80.0, parallel="Gold"),
        ],
        generated_at="2026-09-11T00:00:00+00:00",
    )
    assert payload["metrics"]["exact_matches"] == 0
    assert payload["metrics"]["same_product_variants"] == 1
    group = payload["active_price_comparisons"]["groups"][0]
    assert group["exact_equivalent"] is False
    assert group["comparison_type"] == "SAME_PRODUCT_VARIANTS"
