from pathlib import Path


def test_ui_research_query_uses_exact_variant_discriminators():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "sample.card_number" in html
    assert "sample.parallel" in html
    assert "sample.serial_total" in html
    assert "sample.serial_current" not in html
    assert "sample.grader" in html
    assert "sample.grade" in html
