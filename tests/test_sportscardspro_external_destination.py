from pathlib import Path


def test_sportscardspro_research_link_opens_new_tab():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    needle = 'href="${sportscardsProLink(g)}" target="_blank" rel="noopener"'
    assert needle in html
