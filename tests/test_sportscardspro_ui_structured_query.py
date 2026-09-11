from pathlib import Path


def test_browser_query_uses_structured_fields_not_full_listing_title():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    start = html.index("function researchQuery")
    end = html.index("function sportscardsProLink", start)
    fn = html[start:end]
    assert "sample.title" not in fn
    assert "sample.card_number" in fn
    assert "sample.parallel" in fn
