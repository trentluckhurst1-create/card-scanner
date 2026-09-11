from pathlib import Path


def test_active_market_workflow_detects_untracked_generated_feed():
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "publish-active-market.yml").read_text(encoding="utf-8")
    assert "git status --porcelain -- docs/active_market.json" in workflow
    assert "git diff --quiet -- docs/active_market.json" not in workflow
    assert "contents: write" in workflow
    assert "cron: '17 */6 * * *'" in workflow


def test_active_market_publisher_prints_source_errors_for_diagnosis():
    script = (Path(__file__).resolve().parents[1] / "scripts" / "publish_active_market.py").read_text(encoding="utf-8")
    assert "ACTIVE_SOURCE_" in script
    assert "STORE_ERROR_" in script
    assert "FAIR_VALUE_INCLUDED=NO" in script
    assert "PERSISTENT_HISTORY_CLAIMED=NO" in script
