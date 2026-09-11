from card_scanner.identity_match import exact_components_eligible


def base(**overrides):
    row = {
        "sport": "afl",
        "player": "jamestunstill",
        "year": "2022",
        "brand": "afloptimum",
        "product": "optimum",
        "card_number": "",
        "parallel": "",
        "serial_total": "",
        "grader": "",
        "grade": "",
        "autograph": "0",
        "memorabilia": "0",
        "rookie": "0",
    }
    row.update(overrides)
    return row


def test_card_number_is_strong_enough_for_exact_identity():
    assert exact_components_eligible(base(card_number="41")) is True


def test_numbered_parallel_without_card_number_requires_parallel_and_denominator():
    assert exact_components_eligible(base(parallel="copper", serial_total="170")) is True
    assert exact_components_eligible(base(serial_total="170")) is False
    assert exact_components_eligible(base(parallel="copper")) is False


def test_player_year_product_alone_is_never_exact():
    assert exact_components_eligible(base()) is False


def test_missing_core_identity_is_never_exact():
    assert exact_components_eligible(base(card_number="41", product="")) is False
