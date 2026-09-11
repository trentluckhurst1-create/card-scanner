from card_scanner.sources.gimko import DEFAULT_HEADERS, GimkoSource


def test_gimko_default_client_uses_browser_compatible_headers():
    source = GimkoSource()
    try:
        headers = source.client.headers
        assert "Mozilla/5.0" in headers["User-Agent"]
        assert "Chrome/" in headers["User-Agent"]
        assert headers["Accept-Language"].startswith("en-AU")
        assert headers["Referer"] == "https://www.gimko.com.au/"
        assert "CardScanner" not in headers["User-Agent"]
    finally:
        source.close()


def test_gimko_header_contract_does_not_claim_to_bypass_access_controls():
    assert DEFAULT_HEADERS["Accept"].startswith("text/html")
    assert "Authorization" not in DEFAULT_HEADERS
    assert "Cookie" not in DEFAULT_HEADERS
