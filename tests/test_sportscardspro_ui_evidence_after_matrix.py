from pathlib import Path


def test_external_evidence_follows_store_matrix_and_cards():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    group_start = html.index("function group(g)")
    matrix = html.index("${matrix(ls)}", group_start)
    cards = html.index('class="cards"', group_start)
    evidence = html.index("${evidence(g)}", group_start)
    assert matrix < cards < evidence
