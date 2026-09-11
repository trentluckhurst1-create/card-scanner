from pathlib import Path


def test_the_hobby_is_added_to_cloud_publisher_not_local_cli_scope():
    root = Path(__file__).resolve().parents[1]
    publisher = (root / "scripts" / "publish_active_market.py").read_text(encoding="utf-8")
    cli = (root / "src" / "card_scanner" / "cli.py").read_text(encoding="utf-8")

    assert "TheHobbySource" in publisher
    assert 'NamedStoreSource(name="The Hobby"' in publisher
    assert "TheHobbySource" not in cli
