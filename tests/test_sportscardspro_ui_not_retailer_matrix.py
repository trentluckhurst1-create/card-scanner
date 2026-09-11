from pathlib import Path


def test_matrix_rows_come_only_from_exact_group_listings():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    start = html.index("function matrix(listings)")
    end = html.index("function card(", start)
    matrix_fn = html[start:end]
    assert "SportsCardsPro" not in matrix_fn
