from pathlib import Path


def test_browser_query_includes_serial_denominator():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    start = html.index("function researchQuery")
    end = html.index("function sportscardsProLink", start)
    fn = html[start:end]
    assert "sample.serial_total" in fn
    assert "`/${sample.serial_total}`" in fn
