from pathlib import Path


def test_explainer_links_official_sportscardspro_site():
    html = Path("docs/sportscardspro/index.html").read_text(encoding="utf-8")
    assert 'href="https://www.sportscardspro.com/"' in html
