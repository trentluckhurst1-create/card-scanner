from pathlib import Path


def test_contract_says_sportscardspro_not_active_acquisition_retailer():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "not an active acquisition retailer" in text
