from card_scanner.identity_match import canonical_exact_components, exact_signature


def identity(serial_current):
    return {
        "player": "James Tunstill",
        "year": "2022",
        "brand": "AFL Optimum",
        "set_name": "AFL Optimum",
        "card_number": None,
        "parallel": None,
        "serial_current": serial_current,
        "serial_total": 170,
        "grader": None,
        "grade": None,
        "autograph": True,
        "memorabilia": False,
        "rookie": False,
    }


def test_different_numbered_copies_are_not_exact_same_card():
    copy_87 = canonical_exact_components(sport="AFL", identity=identity(87))
    copy_95 = canonical_exact_components(sport="AFL", identity=identity(95))

    assert copy_87["serial_current"] == "87"
    assert copy_95["serial_current"] == "95"
    assert exact_signature(copy_87) != exact_signature(copy_95)


def test_same_numbered_copy_can_share_exact_signature():
    first = canonical_exact_components(sport="AFL", identity=identity(87))
    second = canonical_exact_components(sport="AFL", identity=identity("087"))

    # Serial copy numbers are numeric identity; leading zero formatting must not
    # turn the same numbered copy into a different card.
    assert exact_signature(first) == exact_signature(second)
