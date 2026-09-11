from __future__ import annotations

from card_scanner.dashboard_export import canonical_family_key
from card_scanner.identity_match import canonical_exact_components


def identity(**overrides):
    base = {
        "player": "Test Player",
        "year": "2025",
        "brand": "Topps",
        "set_name": "Topps Chrome",
        "card_number": "43",
        "parallel": "Silver",
        "serial_total": 99,
        "grader": "PSA",
        "grade": 10,
        "autograph": False,
        "memorabilia": False,
        "rookie": True,
    }
    base.update(overrides)
    return base


def test_brand_prefixed_and_unprefixed_set_names_share_exact_key():
    a = canonical_family_key(sport="NFL", identity=identity(set_name="Topps Chrome"))
    b = canonical_family_key(sport="NFL", identity=identity(set_name="Chrome"))
    assert a == b


def test_numeric_card_number_zero_padding_and_hash_do_not_split_exact_key():
    a = canonical_family_key(sport="NFL", identity=identity(card_number="#043"))
    b = canonical_family_key(sport="NFL", identity=identity(card_number="43"))
    assert a == b


def test_numeric_grade_formatting_does_not_split_exact_key():
    a = canonical_family_key(sport="NFL", identity=identity(grade=10))
    b = canonical_family_key(sport="NFL", identity=identity(grade=10.0))
    assert a == b


def test_material_variant_fields_still_split_exact_key():
    base = canonical_family_key(sport="NFL", identity=identity())
    assert canonical_family_key(sport="NFL", identity=identity(parallel="Gold")) != base
    assert canonical_family_key(sport="NFL", identity=identity(serial_total=50)) != base
    assert canonical_family_key(sport="NFL", identity=identity(autograph=True)) != base
    assert canonical_family_key(sport="NFL", identity=identity(memorabilia=True)) != base
    assert canonical_family_key(sport="NFL", identity=identity(grade=9)) != base


def test_missing_brand_is_not_inferred_from_set_name():
    assert canonical_family_key(sport="NFL", identity=identity(brand=None)) is None


def test_canonical_components_are_explainable():
    components = canonical_exact_components(
        sport="NFL",
        identity=identity(set_name="Topps Chrome", card_number="#043", grade=10.0),
    )
    assert components["brand"] == "topps"
    assert components["product"] == "chrome"
    assert components["card_number"] == "43"
    assert components["grade"] == "10"
