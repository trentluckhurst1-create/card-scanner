from pathlib import Path


def test_sportscardspro_contract_cannot_create_buy_signal():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "cannot create a Card Scanner BUY or STRONG BUY signal by itself" in text
