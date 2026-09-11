from pathlib import Path


def test_contract_forbids_public_republishing_without_permission():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "without express permission" in text
