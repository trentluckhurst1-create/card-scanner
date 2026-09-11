from pathlib import Path


def test_sportscardspro_clean_route_index_exists():
    assert Path("docs/sportscardspro/index.html").exists()
