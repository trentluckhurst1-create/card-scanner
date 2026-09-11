from pathlib import Path


def test_contract_calls_sportscardspro_market_evidence_source():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "market-evidence research source" in text
