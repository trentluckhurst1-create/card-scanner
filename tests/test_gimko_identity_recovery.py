from __future__ import annotations

from card_scanner.identity import parse_identity
from card_scanner.sources.gimko import GimkoSource


def recover(title: str, sport: str):
    return GimkoSource._recover_identity(
        parse_identity(title, sport),
        title=title,
        sport=sport,
    )


def test_recovers_bare_uppercase_catalogue_code_as_card_number():
    identity = recover(
        "2016 AFL Footy Stars Thunder & Lightning Jack Billings TL30 St.Kilda",
        "AFL",
    )

    assert identity.card_number == "TL30"
    assert identity.brand == "Select"
    assert identity.set_name == "Select AFL Footy Stars"
    assert identity.year == "2016"


def test_recovers_second_common_bare_catalogue_code():
    identity = recover(
        "2016 AFL Footy Stars Orange Star Burst Taylor Adams SB13 Collingwood",
        "AFL",
    )

    assert identity.card_number == "SB13"


def test_recovers_explicit_no_card_number_without_confusing_serial_numerator():
    identity = recover(
        "2013-14 Panini Elite John Stockton Die-cut Aspirations Blue No. 63 Utah Jazz",
        "NBA",
    )

    assert identity.card_number == "63"

    serial_identity = recover(
        "2014 Select AFL Future Force Sam Bevan Green Draft Signature Card Low No. 7/40",
        "AFL",
    )
    assert serial_identity.card_number is None
    assert serial_identity.serial_current == 7
    assert serial_identity.serial_total == 40


def test_recovers_explicit_print_run_total_without_inventing_serial_current():
    identity = recover(
        "2004-05 Upper Deck SPx Louis Williams Rookie Jersey Auto Spectrum #'d to 25",
        "NBA",
    )

    assert identity.serial_current is None
    assert identity.serial_total == 25


def test_numbered_to_language_recovers_serial_total():
    identity = recover(
        "2019 Panini Prizm NFL Example Player Silver numbered to 99",
        "NFL",
    )

    assert identity.serial_current is None
    assert identity.serial_total == 99


def test_recovery_does_not_guess_missing_year_or_card_number():
    identity = recover(
        "Panini Prizm Example Player Base Card",
        "NBA",
    )

    assert identity.year is None
    assert identity.card_number is None
    assert identity.serial_total is None


def test_recovery_does_not_relabel_teamcoach_as_select():
    identity = recover(
        "2015 AFL TeamCoach Box",
        "AFL",
    )

    assert identity.brand is None
    assert identity.set_name is None


def test_recovery_never_changes_existing_shared_parser_card_number():
    identity = recover(
        "2024 Select AFL Footy Stars NICK DAICOS Green 7/70 #10",
        "AFL",
    )

    assert identity.card_number == "10"
    assert identity.serial_current == 7
    assert identity.serial_total == 70
