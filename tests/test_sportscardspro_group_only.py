from pathlib import Path


def test_sportscardspro_link_is_rendered_inside_exact_group_component():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "${evidence(g)}" in html
    assert "function group(g)" in html
