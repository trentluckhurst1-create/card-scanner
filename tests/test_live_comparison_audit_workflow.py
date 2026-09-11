from pathlib import Path


def test_live_comparison_audit_targets_automated_active_market_feed():
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "live-comparison-audit.yml").read_text(encoding="utf-8")
    assert "docs/active_market.json" in workflow
    assert "--feed docs/active_market.json" in workflow
    assert "live_active_comparison_audit.json" in workflow
    assert "live-active-comparison-audit" in workflow
