from pathlib import Path


def test_cloud_workflow_does_not_fetch_sportscardspro():
    workflow = Path(".github/workflows/publish-active-market.yml").read_text(encoding="utf-8").lower()
    assert "sportscardspro" not in workflow
