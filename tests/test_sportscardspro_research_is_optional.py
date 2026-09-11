from pathlib import Path


def test_exact_feed_generation_has_no_sportscardspro_import():
    text = Path("scripts/publish_exact_comparisons.py").read_text(encoding="utf-8")
    assert "sportscardspro_reference" not in text
