from pathlib import Path


def test_contract_requires_eligible_subscription_for_future_api():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "eligible SportsCardsPro subscription/API token" in text
