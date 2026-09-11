from pathlib import Path


def test_contract_says_exact_comparison_remains_between_retailers():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "Exact-card comparison remains between active retailer listings" in text
