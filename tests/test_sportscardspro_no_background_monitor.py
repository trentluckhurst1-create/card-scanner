from pathlib import Path


def test_workflows_do_not_background_monitor_sportscardspro():
    for path in Path(".github/workflows").glob("*.yml"):
        assert "sportscardspro" not in path.read_text(encoding="utf-8").lower()
