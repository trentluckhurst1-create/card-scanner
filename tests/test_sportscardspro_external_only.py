from pathlib import Path


def test_compare_public_evidence_copy_is_link_only():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "Their price and historic-sale data stays on their site" in html
