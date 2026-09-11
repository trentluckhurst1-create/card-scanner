from pathlib import Path


def test_sorting_uses_exact_group_active_ask_fields_only():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    start = html.index("function render()")
    end = html.index("async function load()", start)
    render_fn = html[start:end]
    assert "lowest_active_ask_aud" in render_fn
    assert "spread_aud" in render_fn
    assert "SportsCardsPro" not in render_fn
