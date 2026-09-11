from card_scanner.sportscardspro_reference import search_url_for_exact_group


def test_reference_url_does_not_include_retailer_price():
    group = {
        "year": "2024",
        "player": "Player",
        "product": "Product",
        "listings": [{
            "card_number": "12",
            "parallel": "Blue",
            "serial_total": 99,
            "asking_price": 123.45,
            "landed_aud": 130.00,
        }],
    }
    url = search_url_for_exact_group(group)
    assert "123" not in url
    assert "130" not in url
