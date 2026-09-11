from pathlib import Path


def test_explainer_preserves_same_print_run_rule():
    html = Path("docs/sportscardspro/index.html").read_text(encoding="utf-8")
    assert "1/10 and 8/10 are the same numbered card variant" in html
    assert "/10 and /25 are different variants" in html
