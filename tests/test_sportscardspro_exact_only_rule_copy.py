from pathlib import Path


def test_evidence_panel_says_exact_card_print_run():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "Check this exact card/print-run on SportsCardsPro" in html
    assert "Different variants are deliberately not compared" in html
