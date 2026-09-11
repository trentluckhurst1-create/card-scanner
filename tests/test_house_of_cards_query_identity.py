from __future__ import annotations

import httpx

from card_scanner.sources.house_of_cards import HouseOfCardsSource


def test_house_of_cards_rejects_weak_identity_without_card_number_or_serial_parallel() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/shop":
            return httpx.Response(200, text='<a href="/product/weak-card">weak</a>')
        if request.url.path == "/product/weak-card":
            return httpx.Response(
                200,
                text='<h1>2018 Panini Donruss Optic Trae Young Rookie PSA 8</h1><div>$99.00</div>',
            )
        raise AssertionError(str(request.url))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows = HouseOfCardsSource(client=client).search("NBA", "Trae Young")

    assert rows == []
