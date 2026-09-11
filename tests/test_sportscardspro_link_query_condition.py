from pathlib import Path


def test_browser_query_includes_grader_and_grade():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    start = html.index("function researchQuery")
    end = html.index("function sportscardsProLink", start)
    fn = html[start:end]
    assert "sample.grader" in fn
    assert "sample.grade" in fn
