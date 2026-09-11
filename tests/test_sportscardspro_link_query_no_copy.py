from pathlib import Path


def test_browser_query_does_not_use_individual_serial_copy():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    start = html.index("function researchQuery")
    end = html.index("function sportscardsProLink", start)
    fn = html[start:end]
    assert "serial_current" not in fn
    assert "serial_total" in fn
