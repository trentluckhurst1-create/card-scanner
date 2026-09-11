from pathlib import Path


def test_group_template_contains_single_evidence_panel_call():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert html.count("${evidence(g)}") == 1
