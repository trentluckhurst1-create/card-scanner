from pathlib import Path


def test_live_compare_source_health_covers_cloud_sources():
    html = (Path(__file__).resolve().parents[1] / "docs" / "live-compare.html").read_text(encoding="utf-8")

    assert "Cherry" in html
    assert "Sports Card Store" in html
    assert "Gimko" in html
    assert "Urban Empire" in html
    assert "The Hobby" in html
    assert "Eastside Collectables" in html
    assert "unavailable to cloud scan" in html
    assert "no live singles" in html
