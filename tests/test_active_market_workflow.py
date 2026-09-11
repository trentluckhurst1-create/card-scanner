from pathlib import Path


def test_active_market_workflow_detects_untracked_generated_feeds():
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "publish-active-market.yml").read_text(encoding="utf-8")
    assert "git status --porcelain -- docs/active_market.json docs/comparison.json" in workflow
    assert "git add -- docs/active_market.json docs/comparison.json" in workflow
    assert "git diff --quiet -- docs/active_market.json" not in workflow
    assert "contents: write" in workflow
    assert "cron: '17 */6 * * *'" in workflow


def test_active_market_workflow_uses_expanded_discovery_depth():
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "publish-active-market.yml").read_text(encoding="utf-8")
    assert "--limit-per-store-per-sport 400" in workflow
    assert "--deep-overlap-targets 150" in workflow
    assert "--deep-results-per-store 200" in workflow
    assert "--exact-discovery-targets 160" in workflow
    assert "--exact-results-per-store 200" in workflow
    assert "--max-targets 240" in workflow
    assert "--results-per-target 75" in workflow


def test_active_market_refresh_is_self_contained():
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "publish-active-market.yml").read_text(encoding="utf-8")
    assert "scripts/publish_exact_comparisons.py --feed docs/active_market.json --output docs/comparison.json" in workflow
    assert "scripts/audit_live_comparisons.py --feed docs/active_market.json" in workflow
    assert "scripts/audit_identity_completeness.py --feed docs/active_market.json" in workflow
    assert "active-market-refresh-audits" in workflow
    assert "pages: write" in workflow
    assert "id-token: write" in workflow
    assert "actions/configure-pages@v5" in workflow
    assert "actions/upload-pages-artifact@v3" in workflow
    assert "actions/deploy-pages@v4" in workflow


def test_active_market_publisher_prints_source_errors_for_diagnosis():
    script = (Path(__file__).resolve().parents[1] / "scripts" / "publish_active_market.py").read_text(encoding="utf-8")
    assert "ACTIVE_SOURCE_" in script
    assert "STORE_ERROR_" in script
    assert "FAIR_VALUE_INCLUDED=NO" in script
    assert "PERSISTENT_HISTORY_CLAIMED=NO" in script
