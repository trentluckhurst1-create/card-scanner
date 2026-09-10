from card_scanner.identity import parse_identity


def test_live_gold_disco_is_not_truncated_to_disco():
    identity = parse_identity(
        "2020 Panini Prizm ZACK MOSS Rookie Gold Disco 04/10 #343 PSA 9",
        "NFL",
    )

    assert identity.player == "Zack Moss"
    assert identity.parallel == "Gold Disco"
    assert identity.serial_current == 4
    assert identity.serial_total == 10
    assert identity.card_number == "343"
    assert identity.grader == "PSA"
    assert identity.grade == 9.0


def test_live_purple_ice_is_not_truncated_to_purple():
    identity = parse_identity(
        "2020 Panini Prizm PATRICK MAHOMES II Purple Ice Prizm #2",
        "NFL",
    )

    assert identity.player == "Patrick Mahomes II"
    assert identity.parallel == "Purple Ice"
    assert identity.card_number == "2"


def test_eye_black_phrase_does_not_create_black_parallel():
    identity = parse_identity(
        "2022 Panini Immaculate GARRETT WILSON Rookie Eye Black Auto /99 #EB-GW",
        "NFL",
    )

    assert identity.player == "Garrett Wilson"
    assert identity.parallel is None
    assert identity.serial_total == 99
    assert identity.card_number == "EB-GW"
    assert identity.rookie is True
    assert identity.autograph is True


def test_serial_10_of_10_does_not_become_card_number_without_card_marker():
    identity = parse_identity(
        "2019-20 Absolute Memorabilia Rookie Autographs "
        "MATISSE THYBULLE Level 3 10/10 BGS 8.5 Auto 10",
        "NBA",
    )

    assert identity.player == "Matisse Thybulle"
    assert identity.serial_current == 10
    assert identity.serial_total == 10
    assert identity.card_number is None
    assert identity.grader == "BGS"
    assert identity.grade == 8.5


def test_existing_plain_disco_identity_remains_disco():
    identity = parse_identity(
        "2020 Panini Prizm ZACK MOSS Rookie Disco 04/10 #343 PSA 9",
        "NFL",
    )

    assert identity.parallel == "Disco"


def test_existing_plain_purple_identity_remains_purple():
    identity = parse_identity(
        "2023 Panini Prizm PATRICK MAHOMES II Purple 44/225 #2 SGC 9.5",
        "NFL",
    )

    assert identity.parallel == "Purple"
