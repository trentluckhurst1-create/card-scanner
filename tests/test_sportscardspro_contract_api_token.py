from pathlib import Path


def test_contract_explicitly_requires_secret_api_token():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "Keep the token secret" in text
