from pathlib import Path


def test_explainer_says_historic_sales_need_separate_authorization():
    html = Path("docs/sportscardspro/index.html").read_text(encoding="utf-8")
    assert "does not provide historic sales" in html
    assert "separately authorized method" in html
