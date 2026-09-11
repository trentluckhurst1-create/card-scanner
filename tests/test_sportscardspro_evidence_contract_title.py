from pathlib import Path


def test_sportscardspro_evidence_contract_exists_and_is_titled():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert text.startswith("# SportsCardsPro Evidence Contract")
