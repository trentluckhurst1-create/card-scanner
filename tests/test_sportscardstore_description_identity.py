from card_scanner.identity import parse_identity
from card_scanner.sources.sportscardstore import SportsCardStoreSource


def test_recovers_explicit_card_number_from_shopify_description():
    identity = parse_identity(
        "2003 Topps LeBron James RC Rookie NBA Basketball Card PSA 8",
        "NBA",
    )
    assert identity.card_number is None

    recovered = SportsCardStoreSource._recover_identity_from_product(
        identity,
        product={
            "body_html": "<p>The 2003 Topps LeBron James Rookie Card #221 is iconic.</p>"
        },
    )
    assert recovered.card_number == "221"


def test_does_not_treat_serial_fraction_as_card_number():
    identity = parse_identity(
        "Matisse Thybulle Rookie Autograph BGS 8.5",
        "NBA",
    )
    recovered = SportsCardStoreSource._recover_identity_from_product(
        identity,
        product={"body_html": "<p>This card #10/10 is serial numbered.</p>"},
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
