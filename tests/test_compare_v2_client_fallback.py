from __future__ import annotations

from pathlib import Path


def test_compare_page_recomputes_v2_exact_keys_from_current_catalogue():
    html = (Path(__file__).resolve().parents[1] / "docs" / "compare.html").read_text(encoding="utf-8")
    assert "function keyExactV2" in html
    assert "cardNo(i.card_number)" in html
    assert "grade(i.grade)" in html
    assert "productParts(c)" in html
    assert "groupBy(cards,keyExactV2,'EXACT_CARD')" in html
    assert "V2 client comparison from current active catalogue" in html


def test_compare_v2_fallback_keeps_material_variant_fields_in_exact_key():
    html = (Path(__file__).resolve().parents[1] / "docs" / "compare.html").read_text(encoding="utf-8")
    exact_key_line = next(line for line in html.splitlines() if "function keyExactV2" in line)
    for field in ("i.parallel", "i.serial_total", "i.grader", "i.grade", "i.autograph", "i.memorabilia", "i.rookie"):
        assert field in exact_key_line
