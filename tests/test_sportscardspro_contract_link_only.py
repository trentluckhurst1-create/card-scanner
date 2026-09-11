from pathlib import Path


def test_contract_states_exact_comparison_may_link_to_sportscardspro():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "may link the user to a SportsCardsPro search" in text
