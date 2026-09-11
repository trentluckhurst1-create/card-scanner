from pathlib import Path


def test_public_guard_states_proprietary_price_data_not_copied():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "SportsCardsPro is linked as an external research source" in html
    assert "proprietary pricing data is not copied" in html
