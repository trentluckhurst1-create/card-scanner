from pathlib import Path


def test_explainer_mentions_express_written_permission_boundary():
    html = Path("docs/sportscardspro/index.html").read_text(encoding="utf-8")
    assert "express written permission" in html
