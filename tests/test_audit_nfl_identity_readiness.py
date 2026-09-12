from scripts.audit_nfl_identity_readiness import exact_ready


def card(identity, eligible=None):
    row = {"identity": identity}
    if eligible is not None:
        row["card_family"] = {"eligible": eligible}
    return row


def test_exact_ready_prefers_existing_family_eligibility():
    assert exact_ready(card({}, eligible=True)) is True


def test_exact_ready_requires_base_identity_and_number_or_named_serial_parallel():
    base = {"player": "Patrick Mahomes II", "year": "2021", "brand": "Panini Prizm", "set_name": "Panini Prizm"}
    assert exact_ready(card({**base, "card_number": "190"})) is True
    assert exact_ready(card({**base, "parallel": "Purple Ice", "serial_total": 225})) is True
    assert exact_ready(card({**base, "parallel": "Purple Ice"})) is False
    assert exact_ready(card({"player": "Patrick Mahomes II", "card_number": "190"})) is False
