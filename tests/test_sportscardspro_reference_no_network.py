from pathlib import Path


def test_reference_helper_performs_no_network_requests():
    text = Path("src/card_scanner/sportscardspro_reference.py").read_text(encoding="utf-8").lower()
    for forbidden in ("requests", "urllib.request", "httpx", "aiohttp", "urlopen"):
        assert forbidden not in text
