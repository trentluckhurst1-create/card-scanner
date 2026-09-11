from pathlib import Path


def test_exact_feed_metrics_have_no_sportscardspro_counts():
    text = Path("scripts/publish_exact_comparisons.py").read_text(encoding="utf-8").lower()
    assert "sportscardspro" not in text
