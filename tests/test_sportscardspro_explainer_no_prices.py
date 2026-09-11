from pathlib import Path
import re


def test_explainer_contains_no_dollar_price_values():
    html = Path("docs/sportscardspro/index.html").read_text(encoding="utf-8")
    assert re.search(r"\$\d", html) is None
