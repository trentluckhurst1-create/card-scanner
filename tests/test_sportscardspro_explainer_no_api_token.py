from pathlib import Path


def test_explainer_contains_no_api_token_value():
    html = Path("docs/sportscardspro/index.html").read_text(encoding="utf-8")
    assert "?t=" not in html
    assert "API token:" not in html
