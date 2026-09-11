from pathlib import Path


def test_explainer_states_no_public_redistribution_without_permission():
    html = Path("docs/sportscardspro/index.html").read_text(encoding="utf-8")
    assert "prohibit third-party software from redistributing the pricing data without express written permission" in html
