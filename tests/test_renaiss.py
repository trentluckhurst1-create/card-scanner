from card_scanner.identity import parse_identity
from card_scanner.renaiss import RenaissSoldCompProvider


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, search_payload, trades_payload):
        self.search_payload = search_payload
        self.trades_payload = trades_payload
        self.calls = []

    def get(self, url, params=None):
        self.calls.append((url, params))

        if url.endswith("/v1/search"):
            return FakeResponse(self.search_payload)

        return FakeResponse(self.trades_payload)


class FakeFx:
    def convert_to_aud(self, amount, currency, sold_date):
        class Result:
            aud_amount = amount * 1.5
            status = "TEST"
            source = "TEST_FX"
            rate_date = sold_date

        return Result()


def target():
    return parse_identity(
        "Victor Wembanyama 2023 Panini Select #87 Blue Prizm PSA 10",
        "NBA",
    )


def matching_item():
    return {
        "id": "item-1",
        "name": "Victor Wembanyama",
        "game": "sports",
        "setName": "Panini Select",
        "cardNumber": "87",
        "variation": "Blue Prizm",
        "company": "PSA",
        "grade": "10 Gem Mint",
        "gradeLabel": "PSA 10",
        "href": (
            "/card/sports/panini-select/"
            "87-victor-wembanyama-psa-10-item1"
        ),
    }


def transaction(price=15000, detail="sale-1"):
    return {
        "currency": "USD",
        "priceMinor": price,
        "priceUsdCents": price,
        "source": "site_a",
        "company": "PSA",
        "grade": "10 Gem Mint",
        "kind": "transaction",
        "category": "public",
        "observedAt": "2026-09-07T00:00:00.000Z",
        "detail": detail,
        "timeGranularity": "day",
    }


def listing(price=100):
    row = transaction(price=price, detail="live-1")
    row["kind"] = "listing"
    row["observedAt"] = "2026-09-07T12:34:56.000Z"
    return row


def test_generic_query_only_interface_returns_no_evidence():
    provider = RenaissSoldCompProvider(
        client=FakeClient({}, {}),
        fx_provider=FakeFx(),
    )

    assert provider.sold_comps("NBA", "Victor Wembanyama") == []
    assert provider.query_count == 0


def test_transaction_only_rows_become_sold_comps():
    client = FakeClient(
        {"results": [matching_item()]},
        {"trades": [listing(), transaction()]},
    )
    provider = RenaissSoldCompProvider(
        client=client,
        fx_provider=FakeFx(),
    )

    comps = provider.sold_comps_for_identity(
        "NBA",
        target(),
        "Victor Wembanyama",
        50,
    )

    assert len(comps) == 1
    assert comps[0].sale_id == "sale-1"
    assert comps[0].sold_price == 150.0
    assert comps[0].sold_price_aud == 225.0
    assert comps[0].sale_type == "transaction"
    assert comps[0].source == "renaiss_transaction"
    assert "LISTING_ROWS_EXCLUDED=TRUE" in comps[0].notes
    assert provider.query_count == 2


def test_wrong_card_search_result_never_fetches_trades():
    wrong = matching_item()
    wrong["setName"] = "Court Kings"
    wrong["cardNumber"] = "7"

    client = FakeClient(
        {"results": [wrong]},
        {"trades": [transaction()]},
    )
    provider = RenaissSoldCompProvider(
        client=client,
        fx_provider=FakeFx(),
    )

    comps = provider.sold_comps_for_identity(
        "NBA",
        target(),
        "Victor Wembanyama",
        50,
    )

    assert comps == []
    assert provider.query_count == 1
    assert len(client.calls) == 1


def test_parallel_mismatch_is_rejected_before_trade_call():
    wrong = matching_item()
    wrong["variation"] = "Tri-Color"

    client = FakeClient(
        {"results": [wrong]},
        {"trades": [transaction()]},
    )
    provider = RenaissSoldCompProvider(
        client=client,
        fx_provider=FakeFx(),
    )

    comps = provider.sold_comps_for_identity(
        "NBA",
        target(),
        "Victor Wembanyama",
        50,
    )

    assert comps == []
    assert provider.query_count == 1


def test_grade_mismatch_is_rejected_before_trade_call():
    wrong = matching_item()
    wrong["grade"] = "9 Mint"
    wrong["gradeLabel"] = "PSA 9"

    client = FakeClient(
        {"results": [wrong]},
        {"trades": [transaction()]},
    )
    provider = RenaissSoldCompProvider(
        client=client,
        fx_provider=FakeFx(),
    )

    comps = provider.sold_comps_for_identity(
        "NBA",
        target(),
        "Victor Wembanyama",
        50,
    )

    assert comps == []
    assert provider.query_count == 1


def test_duplicate_transaction_ids_are_deduped():
    client = FakeClient(
        {"results": [matching_item()]},
        {
            "trades": [
                transaction(detail="same-sale"),
                transaction(detail="same-sale"),
            ]
        },
    )
    provider = RenaissSoldCompProvider(
        client=client,
        fx_provider=FakeFx(),
    )

    comps = provider.sold_comps_for_identity(
        "NBA",
        target(),
        "Victor Wembanyama",
        50,
    )

    assert len(comps) == 1


def test_session_memory_cache_avoids_repeat_network_calls():
    client = FakeClient(
        {"results": [matching_item()]},
        {"trades": [transaction()]},
    )
    provider = RenaissSoldCompProvider(
        client=client,
        fx_provider=FakeFx(),
    )

    first = provider.sold_comps_for_identity(
        "NBA",
        target(),
        "Victor Wembanyama",
        50,
    )
    second = provider.sold_comps_for_identity(
        "NBA",
        target(),
        "Victor Wembanyama",
        50,
    )

    assert len(first) == 1
    assert len(second) == 1
    assert provider.query_count == 2
    assert len(client.calls) == 2


def test_non_transaction_feed_produces_zero_sold_evidence():
    client = FakeClient(
        {"results": [matching_item()]},
        {"trades": [listing(100), listing(119900)]},
    )
    provider = RenaissSoldCompProvider(
        client=client,
        fx_provider=FakeFx(),
    )

    comps = provider.sold_comps_for_identity(
        "NBA",
        target(),
        "Victor Wembanyama",
        50,
    )

    assert comps == []

def test_structured_title_does_not_invent_year():
    provider = RenaissSoldCompProvider(
        client=FakeClient({}, {}),
        fx_provider=FakeFx(),
    )

    title = provider._structured_title(matching_item())
    identity = parse_identity(title, "NBA")

    assert identity.player == "Victor Wembanyama"
    assert identity.set_name == "Panini Select"
    assert identity.card_number == "87"
    assert identity.grader == "PSA"
    assert identity.grade == 10.0
    assert identity.year is None


def test_renaiss_comp_missing_year_is_rejected_by_strict_matcher():
    from card_scanner.sold_comp_engine import assess_strict_sold_comp

    client = FakeClient(
        {"results": [matching_item()]},
        {"trades": [transaction()]},
    )
    provider = RenaissSoldCompProvider(
        client=client,
        fx_provider=FakeFx(),
    )

    source = target()

    comps = provider.sold_comps_for_identity(
        "NBA",
        source,
        "Victor Wembanyama",
        50,
    )

    assert len(comps) == 1
    assert comps[0].identity.year is None

    match = assess_strict_sold_comp(
        "target-listing",
        source,
        comps[0],
    )

    assert match.match_level.value == "REJECT"
    assert "candidate year missing" in match.rejection_reasons


def test_provider_cannot_bypass_generic_production_engine():
    provider = RenaissSoldCompProvider(
        client=FakeClient(
            {"results": [matching_item()]},
            {"trades": [transaction()]},
        ),
        fx_provider=FakeFx(),
    )

    result = provider.sold_comps(
        "NBA",
        "Victor Wembanyama",
        50,
    )

    assert result == []
    assert provider.query_count == 0