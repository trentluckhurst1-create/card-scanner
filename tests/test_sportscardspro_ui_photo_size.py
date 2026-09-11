from pathlib import Path


def test_exact_comparison_photos_have_uniform_fixed_height():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert ".card-image{width:100%;height:120px" in html
    assert ".card-image img{width:100%;height:100%;object-fit:contain}" in html
