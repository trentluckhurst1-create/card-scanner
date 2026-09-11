from pathlib import Path


def test_contract_allows_link_to_same_card_identity_search():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "same card identity" in text
