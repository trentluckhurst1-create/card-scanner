from pathlib import Path


def test_compare_does_not_fetch_sportscardspro_in_javascript():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "fetch('https://www.sportscardspro.com" not in html
    assert 'href="${sportscardsProLink(g)}"' in html
