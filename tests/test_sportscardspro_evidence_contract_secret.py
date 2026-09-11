from pathlib import Path


def test_contract_future_api_token_is_secret():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "Keep the token secret" in text
