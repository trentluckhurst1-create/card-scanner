from pathlib import Path


def test_contract_forbids_persisting_sportscardspro_price_history_data():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "does not scrape, cache, persist, export, or republish" in text
