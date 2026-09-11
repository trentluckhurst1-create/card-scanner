from pathlib import Path


def test_contract_requires_separate_authorized_history_mechanism():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "historic-sales integration must use a separately authorized mechanism" in text
