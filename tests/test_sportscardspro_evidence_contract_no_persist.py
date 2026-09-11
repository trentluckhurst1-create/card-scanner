from pathlib import Path


def test_contract_explicitly_says_no_persist():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "persist" in text
