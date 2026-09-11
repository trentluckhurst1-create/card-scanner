from pathlib import Path


def test_contract_distinguishes_current_api_values_from_historic_sales():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "current condition values" in text
    assert "historic sales are not available" in text
