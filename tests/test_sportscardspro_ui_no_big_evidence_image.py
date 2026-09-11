from pathlib import Path


def test_evidence_panel_contains_no_image():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    start = html.index("function evidence(g)")
    end = html.index("function group(g)", start)
    assert "<img" not in html[start:end]
