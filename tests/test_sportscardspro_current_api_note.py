from pathlib import Path


def test_future_api_contract_says_current_values_only():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "current condition values" in text
