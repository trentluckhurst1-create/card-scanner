from pathlib import Path


def test_store_count_is_read_from_exact_group_not_sportscardspro():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "${g.store_count||0} stores" in html
