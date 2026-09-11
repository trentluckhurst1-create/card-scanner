from pathlib import Path


def test_contract_future_integration_uses_documented_api_csv():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "documented API/CSV service" in text
