from pathlib import Path


def test_contract_does_not_claim_documented_api_provides_historic_sales():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "historic sales are not available through those API/CSV endpoints" in text
