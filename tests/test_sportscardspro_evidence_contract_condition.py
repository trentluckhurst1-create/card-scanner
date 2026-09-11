from pathlib import Path


def test_contract_calls_future_api_values_condition_values():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "current condition values" in text
