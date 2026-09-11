from pathlib import Path


def test_evidence_contract_documents_serial_copy_semantics():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "1/10 vs 8/10" in text
    assert "Different print runs are different variants" in text
