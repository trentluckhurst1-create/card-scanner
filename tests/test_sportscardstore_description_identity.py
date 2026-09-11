from card_scanner.identity import parse_identity
from card_scanner.sources.sportscardstore import SportsCardStoreSource


def _base_identity():
    return parse_identity(
        "2003 Topps LeBron James RC Rookie NBA Basketball Card PSA 8",
        "NBA",
    )


def test_recovers_explicit_card_number_from_shopify_description():
    identity = _base_identity()
    assert identity.card_number is None

    recovered = SportsCardStoreSource._recover_identity_from_product(
        identity,
        product={
            "body_html": "<p>The 2003 Topps LeBron James Rookie Card #221 is iconic.</p>"
        },
    )
    assert recovered.card_number == "221"


def test_recovers_no_and_card_number_description_variants():
    for body_html, expected in (
        ("<p>No. 221</p>", "221"),
        ("<p>Card Number: 22A</p>", "22A"),
        ("<p>Card No: RS-15</p>", "RS-15"),
    ):
        recovered = SportsCardStoreSource._recover_identity_from_product(
            _base_identity(),
            product={"body_html": body_html},
        )
        assert recovered.card_number == expected


def test_does_not_treat_serial_fraction_or_unlabelled_number_as_card_number():
    identity = parse_identity(
        "Matisse Thybulle Rookie Autograph BGS 8.5",
        "NBA",
    )
    for body_html in (
        "<p>This card #10/10 is serial numbered.</p>",
        "<p>Limited 75th anniversary release, 221 examples discussed.</p>",
    ):
        recovered = SportsCardStoreSource._recover_identity_from_product(
            identity,
            product={"body_html": body_html},
        )
        assert recovered.card_number is None


def test_description_never_overwrites_title_card_number():
    identity = parse_identity(
        "2003 Topps LeBron James Rookie Card #221 PSA 8",
        "NBA",
    )
    recovered = SportsCardStoreSource._recover_identity_from_product(
        identity,
        product={"body_html": "<p>Card #999.</p>"},
    )
    assert recovered.card_number == "221"
