from pathlib import Path


def test_explainer_scopes_future_api_to_current_condition_values():
    html = Path("docs/sportscardspro/index.html").read_text(encoding="utf-8")
    assert "current condition values directly" in html
