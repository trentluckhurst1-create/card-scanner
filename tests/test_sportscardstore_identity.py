from card_scanner.identity import parse_identity
from card_scanner.risk import title_risk_details


def test_sportscardstore_afl_and_nba_identity_cases() -> None:
    cases = [
        (
            "AFL",
            "2022 Select AFL Patrick Cripps Brownlow Medal Booklet Platinum 20/60 Carlton",
            {
                "player": "Patrick Cripps",
                "serial_current": 20,
                "serial_total": 60,
            },
        ),
        (
            "AFL",
            "2022 SELECT AFL OPTIMUM Sam Darcy Platinum Draft Pick Signature DPS 12/40",
            {
                "player": "Sam Darcy",
                "serial_current": 12,
                "serial_total": 40,
                "autograph": True,
            },
        ),
        (
            "NBA",
            "2019-20 PANINI DONRUSS OPTIC Ja Morant Rated Rookie RC NBA Basketball Card PSA 10",
            {
                "player": "Ja Morant",
                "rookie": True,
                "grader": "PSA",
                "grade": 10.0,
            },
        ),
        (
            "NBA",
            "2019-20 ABSOLUTE MEMORABILIA ROOKIE AUTOGRAPHS Matisse Thybulle Level 3 RC NBA Basketball Card 10/10 BGS 8.5 AUTO 10",
            {
                "player": "Matisse Thybulle",
                "serial_current": 10,
                "serial_total": 10,
                "rookie": True,
                "autograph": True,
                "memorabilia": True,
                "grader": "BGS",
                "grade": 8.5,
            },
        ),
        (
            "NBA",
            "2019-20 PANINI HOOPS Zion Williamson Teal Explosion RC Rookie Basketball Card BGS 9.5",
            {
                "player": "Zion Williamson",
                "parallel": "Teal Explosion",
                "rookie": True,
                "grader": "BGS",
                "grade": 9.5,
            },
        ),
    ]

    for sport, title, expected in cases:
        identity = parse_identity(title, sport)

        for field, value in expected.items():
            assert getattr(identity, field) == value


def test_sportscardstore_matching_pair_is_bundle_risk() -> None:
    title = (
        "Matching Pair 2025 AFL Select Epic Black SAM WALSH "
        "+ Signature Redemption 26/40"
    )

    risks = title_risk_details(title)
    codes = {risk.code for risk in risks}

    assert "LOT_OR_BUNDLE" in codes
    assert "REDEMPTION" in codes
