from scripts.audit_cross_store_overlap import build_overlap_report


def card(source, external_id, *, player="Player One", year="2025", brand="Panini", set_name="Panini Prizm", card_number=None, parallel=None, serial_total=None):
    return {
        "source": source,
        "external_id": external_id,
        "sport": "NBA",
        "title": f"{year} {set_name} {player}",
        "url": f"https://example.test/{external_id}",
        "identity": {
            "player": player,
            "year": year,
            "brand": brand,
            "set_name": set_name,
            "card_number": card_number,
            "parallel": parallel,
            "serial_total": serial_total,
            "grader": None,
            "grade": None,
            "autograph": False,
            "memorabilia": False,
            "rookie": True,
        },
    }


def test_same_product_different_card_number_is_variant_not_exact():
    report = build_overlap_report([
        card("cherry", "1", card_number="101"),
        card("urbanempire", "2", card_number="102"),
    ])
    assert report["bucket_counts"]["SAME_PRODUCT_DIFFERENT_VARIANT"] == 1
    assert report["mismatch_dimension_counts"]["card_number"] == 1
    assert report["governance"]["near_matches_are_exact_equivalents"] is False


def test_same_product_different_parallel_is_variant():
    report = build_overlap_report([
        card("cherry", "1", card_number="101", parallel="Silver"),
        card("sportscardstore", "2", card_number="101", parallel="Red"),
    ])
    assert report["bucket_counts"]["SAME_PRODUCT_DIFFERENT_VARIANT"] == 1
    assert report["mismatch_dimension_counts"]["parallel"] == 1


def test_missing_card_number_is_incomplete_not_equivalent():
    report = build_overlap_report([
        card("cherry", "1", card_number="101", parallel="Silver"),
        card("sportscardstore", "2", card_number=None, parallel="Silver"),
    ])
    assert report["bucket_counts"]["SAME_PRODUCT_INCOMPLETE_IDENTITY"] == 1
    assert report["mismatch_dimension_counts"]["card_number"] == 1


def test_different_products_stay_separate():
    report = build_overlap_report([
        card("cherry", "1", set_name="Panini Prizm", card_number="101"),
        card("urbanempire", "2", set_name="Panini Select", card_number="101"),
    ])
    assert report["bucket_counts"]["DIFFERENT_PRODUCT"] == 1


def test_same_known_identity_is_diagnostic_only():
    report = build_overlap_report([
        card("cherry", "1", card_number="101", parallel="Silver", serial_total="99"),
        card("urbanempire", "2", card_number="101", parallel="Silver", serial_total="99"),
    ])
    assert report["bucket_counts"]["SAME_PRODUCT_SAME_KNOWN_IDENTITY"] == 1
    assert report["same_known_identity_eligibility_counts"]["EXACT_ELIGIBLE_PAIR"] == 1
    assert report["near_match_examples"][0]["exact_eligibility"] == "EXACT_ELIGIBLE_PAIR"
    assert report["governance"]["diagnostics_are_price_comparisons"] is False


def test_same_known_identity_without_discriminator_is_insufficient():
    report = build_overlap_report([
        card("cherry", "1"),
        card("urbanempire", "2"),
    ])
    assert report["bucket_counts"]["SAME_PRODUCT_SAME_KNOWN_IDENTITY"] == 1
    assert report["same_known_identity_eligibility_counts"]["INSUFFICIENT_IDENTITY_PAIR"] == 1
    assert report["near_match_examples"][0]["exact_eligibility"] == "INSUFFICIENT_IDENTITY_PAIR"
    assert report["governance"]["same_known_identity_implies_exact_eligibility"] is False


def test_serial_parallel_same_known_pair_is_exact_eligible_without_card_number():
    report = build_overlap_report([
        card("cherry", "1", parallel="Gold", serial_total="10"),
        card("urbanempire", "2", parallel="Gold", serial_total="10"),
    ])
    assert report["same_known_identity_eligibility_counts"]["EXACT_ELIGIBLE_PAIR"] == 1


def test_same_store_pairs_are_ignored():
    report = build_overlap_report([
        card("cherry", "1", card_number="101"),
        card("cherry", "2", card_number="102"),
    ])
    assert report["cross_store_player_year_pairs"] == 0
    assert report["bucket_counts"] == {}
    assert report["same_known_identity_eligibility_counts"] == {}
