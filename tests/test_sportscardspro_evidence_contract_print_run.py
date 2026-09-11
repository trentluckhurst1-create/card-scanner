from pathlib import Path


def test_contract_says_different_print_runs_are_different_variants():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "Different print runs are different variants" in text
