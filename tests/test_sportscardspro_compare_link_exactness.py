from pathlib import Path


def test_evidence_panel_is_after_exact_cards_in_group_template():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    group_start = html.index("function group(g)")
    cards_pos = html.index('class="cards"', group_start)
    evidence_pos = html.index("${evidence(g)}", group_start)
    assert evidence_pos > cards_pos
