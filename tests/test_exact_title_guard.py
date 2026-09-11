from __future__ import annotations

from card_scanner.active_price_comparison import build_active_price_comparisons


def _card(source: str, external_id: str, title: str, price: float) -> dict:
    return {
        "source": source,
        "external_id": external_id,
        "url": f"https://example.test/{external_id}",
        "title": title,
        "sport": "NBA",
        "asking_price": price,
        "shipping": 0.0,
        "currency": "AUD",
        "landed_aud": price,
        "identity": {
            "player": "Trae Young",
            "year": "2018",
            "brand": "Panini Donruss Optic",
            "set_name": "Panini Donruss Optic",
            "card_number": "198",
            "parallel": None,
            "serial_total": None,
            "grader": "PSA",
            "grade": 8.0,
            "rookie": True,
            "autograph": False,
            "memorabilia": False,
        },
        "card_family": {
            "key": "cf_same_structured_identity",
            "eligible": True,
            "match_confidence": 1.0,
            "match_reasons": [
                "same player",
                "same year",
                "same brand/product",
                "same card number",
                "same grading state",
                "same rookie state",
            ],
        },
    }


def test_choice_dragon_cannot_compare_as_base_when_parallel_parser_misses_it():
    payload = build_active_price_comparisons(
        [
            _card(
                "cherry",
                "dragon",
                "2018 Panini Donruss Optic TRAE YOUNG Rated Rookie Choice Dragon #198 PSA 8",
                499.99,
            ),
            _card(
                "other",
                "base",
                "2018 Panini Donruss Optic TRAE YOUNG Rated Rookie #198 PSA 8",
                35.95,
            ),
        ]
    )

    assert payload["exact_match_count"] == 0


def test_same_choice_dragon_titles_still_compare_across_stores():
    payload = build_active_price_comparisons(
        [
            _card(
                "cherry",
                "a",
                "2018 Panini Donruss Optic TRAE YOUNG Rated Rookie Choice Dragon #198 PSA 8",
                499.99,
            ),
            _card(
                "ebay",
                "b",
                "2018 Panini Donruss Optic Trae Young Choice Dragon Rated Rookie #198 PSA 8",
                420.00,
            ),
        ]
    )

    assert payload["exact_match_count"] == 1
    group = next(group for group in payload["groups"] if group["comparison_type"] == "EXACT_CARD")
    assert group["cheapest_store"] == "ebay"
    assert group["spread_aud"] == 79.99
    assert "title discriminator guard passed" in group["match_reasons"]


def test_bare_card_numbers_split_serial_parallel_candidates():
    def serial_card(source: str, external_id: str, bare_number: int) -> dict:
        card = _card(
            source,
            external_id,
            f"Tyler Ulis 2016-17 Panini Spectra {bare_number} Rookie Jersey Auto Gold RC 7/10",
            50.0,
        )
        card["sport"] = "NBA"
        card["identity"] = {
            "player": "Tyler Ulis",
            "year": "2016-17",
            "brand": "Spectra",
            "set_name": "Spectra",
            "card_number": None,
            "parallel": "Gold",
            "serial_total": 10,
            "grader": None,
            "grade": None,
            "rookie": True,
            "autograph": True,
            "memorabilia": True,
        }
        card["card_family"]["key"] = "cf_same_structured_serial_identity"
        return card

    payload = build_active_price_comparisons(
        [
            serial_card("store-a", "125", 125),
            serial_card("store-b", "138", 138),
        ]
    )

    assert payload["exact_match_count"] == 0
