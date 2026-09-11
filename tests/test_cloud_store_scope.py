from pathlib import Path


def test_expansion_sources_are_added_to_cloud_publisher_not_local_cli_scope():
    root = Path(__file__).resolve().parents[1]
    publisher = (root / "scripts" / "publish_active_market.py").read_text(encoding="utf-8")
    cli = (root / "src" / "card_scanner" / "cli.py").read_text(encoding="utf-8")

    assert "TheHobbySource" in publisher
    assert 'NamedStoreSource(name="The Hobby"' in publisher
    assert "EastsideSource" in publisher
    assert 'NamedStoreSource(name="Eastside Collectables"' in publisher

    assert "TheHobbySource" not in cli
    assert "EastsideSource" not in cli
