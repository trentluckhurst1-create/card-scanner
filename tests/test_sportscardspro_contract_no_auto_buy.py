from pathlib import Path


def test_evidence_contract_has_no_auto_buy_authority():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "cannot create a Card Scanner BUY or STRONG BUY signal by itself" in text
