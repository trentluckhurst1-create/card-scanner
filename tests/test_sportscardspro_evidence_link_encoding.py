from pathlib import Path


def test_browser_evidence_link_uses_encodeURIComponent():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "encodeURIComponent(researchQuery(g))" in html
