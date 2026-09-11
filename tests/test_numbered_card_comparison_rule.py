from card_scanner.identity_match import canonical_exact_components, exact_signature


def identity(current, total):
    return {
        "player": "Player",
        "year": "2025",
        "brand": "Panini",
        "set_name": "Panini Prizm",
        "card_number": "101",
        "parallel": "Gold",
        "serial_current": current,
        "serial_total": total,
        "grader": None,
        "grade": None,
        "autograph": False,
        "memorabilia": False,
        "rookie": True,
    }


def signature(current, total):
    return exact_signature(canonical_exact_components(sport="NFL", identity=identity(current, total)))


def test_same_print_run_different_copy_numbers_compare():
    assert signature(1, 10) == signature(8, 10)


def test_different_print_runs_do_not_compare():
    assert signature(1, 10) != signature(1, 25)
