from pathlib import Path


def test_external_research_links_open_safely():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert 'target="_blank" rel="noopener"' in html
