from pathlib import Path


def test_evidence_contract_requires_authorized_public_display():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "redistribution permission" in text
    assert "Keep the token secret" in text
