from pathlib import Path


def test_sportscardspro_explainer_states_public_data_boundary():
    html = Path("docs/sportscardspro/index.html").read_text(encoding="utf-8")
    assert "external research destination" in html
    assert "1/10 and 8/10" in html
    assert "/10 and /25" in html
    assert "paid API" in html
    assert "historic sales" in html
    assert "https://www.sportscardspro.com/" in html
