from pathlib import Path


def test_ui_has_no_sportscardspro_price_value_fields():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8").lower()
    for field in ("scp_price", "scp_sales", "sportscardspro_value", "sportscardspro_history"):
        assert field not in html
