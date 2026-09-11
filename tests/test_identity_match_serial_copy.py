from card_scanner.identity_match import canonical_exact_components, exact_signature


def identity(serial_current, serial_total=170):
    return {
        "player": "James Tunstill",
        "year": "2022",
        "brand": "AFL Optimum",
        "set_name": "AFL Optimum",
        "card_number": None,
        "parallel": None,
        "serial_current": serial_current,
        "serial_total": serial_total,
        "grader": None,
        "grade": None,
        "autograph": True,
        "memorabilia": False,
        "rookie": False,
    }


def test_different_copy_numbers_same_print_run_are_comparable():
    copy_1 = canonical_exact_components(sport="AFL", identity=identity(1, 10))
    copy_8 = canonical_exact_components(sport="AFL", identity=identity(8, 10))

    # Individual serial copy number is not variant identity. 1/10 and 8/10 are
    # the same card variant for store-price comparison purposes.
    assert "serial_current" not in copy_1
    assert exact_signature(copy_1) == exact_signature(copy_8)


def test_different_print_runs_are_not_exact_same_card_variant():
    out_of_10 = canonical_exact_components(sport="AFL", identity=identity(1, 10))
    out_of_25 = canonical_exact_components(sport="AFL", identity=identity(1, 25))

    assert exact_signature(out_of_10) != exact_signature(out_of_25)
