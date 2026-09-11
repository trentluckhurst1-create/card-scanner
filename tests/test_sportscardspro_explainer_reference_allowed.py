from pathlib import Path


def test_explainer_states_external_reference_with_link_boundary():
    html = Path("docs/sportscardspro/index.html").read_text(encoding="utf-8")
    assert "allow external references with attribution and a visible link" in html
