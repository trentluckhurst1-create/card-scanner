from pathlib import Path


def test_guard_keeps_active_asks_separate_from_fair_value():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "Active asks are comparison evidence only, not fair value" in html
