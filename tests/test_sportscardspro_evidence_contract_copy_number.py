from pathlib import Path


def test_contract_says_same_print_run_copy_numbers_are_comparable():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "individual copy numbers within the same print run are comparable" in text
