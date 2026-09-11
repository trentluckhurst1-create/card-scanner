from pathlib import Path


def test_identity_completeness_audit_contract():
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "audit_identity_completeness.py").read_text(encoding="utf-8")
    workflow = (root / ".github" / "workflows" / "identity-completeness-audit.yml").read_text(encoding="utf-8")

    assert "PLAYER_YEAR_READY" in script
    assert "PRODUCT_READY" in script
    assert "EXACT_READY" in script
    assert "card_number_coverage_pct" in script
    assert "parallel_coverage_pct" in script
    assert "docs/active_market.json" in workflow
    assert "identity-completeness-audit" in workflow
