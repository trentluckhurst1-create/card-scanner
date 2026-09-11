from pathlib import Path


def test_compare_empty_state_still_rejects_different_variants():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "Different variants are deliberately not compared" in html
