from card_scanner.identity import parse_identity
from card_scanner.models import Listing
from card_scanner.underdescription import assess_underdescription


def make_listing(title: str, sport: str = 'NFL') -> Listing:
    return Listing(
        source='Test Store',
        external_id='test-1',
        url='https://example.com/test-1',
        title=title,
        sport=sport,
        price=100.0,
        identity=parse_identity(title, sport),
    )


def test_complete_specific_title_is_clear():
    listing = make_listing(
        '2020 Donruss Optic CeeDee Lamb Rated Rookie Green Velocity #156 PSA 10'
    )
    result = assess_underdescription(listing)

    assert result.status == 'CLEAR'
    assert result.risk_score == 0.0
    assert result.signal_codes == ()
    assert 'CARD_NUMBER_SPECIFIED' in result.evidence_flags
    assert 'PARALLEL_SPECIFIED' in result.evidence_flags
    assert 'GRADING_SPECIFIED' in result.evidence_flags


def test_generic_player_listing_is_reviewed():
    listing = make_listing('CeeDee Lamb Football Card')
    result = assess_underdescription(listing)

    assert result.status in {'REVIEW', 'POOR_IDENTITY'}
    assert 'MISSING_YEAR' in result.signal_codes
    assert 'MISSING_PRODUCT' in result.signal_codes
    assert 'GENERIC_PLAYER_LISTING' in result.signal_codes


def test_missing_player_is_poor_identity():
    listing = make_listing('2024 Panini Prizm Gold /10 #101')
    result = assess_underdescription(listing)

    assert result.status == 'POOR_IDENTITY'
    assert 'MISSING_PLAYER' in result.signal_codes
    assert 'SERIAL_WITH_WEAK_IDENTITY' in result.signal_codes


def test_serial_specificity_is_evidence_not_hidden_attribute_inference():
    listing = make_listing(
        '2024 Panini Prizm Joe Burrow Gold 7/10 #55'
    )
    result = assess_underdescription(listing)

    assert 'SERIAL_SPECIFIED' in result.evidence_flags
    assert 'CARD_NUMBER_SPECIFIED' in result.evidence_flags
    assert 'SERIAL_WITH_WEAK_IDENTITY' not in result.signal_codes


def test_incomplete_grading_label_is_flagged():
    listing = make_listing(
        '2024 Panini Prizm Joe Burrow Silver #55 PSA'
    )
    result = assess_underdescription(listing)

    assert 'GRADE_LABEL_INCOMPLETE' in result.signal_codes
    assert 'GRADING_SPECIFIED' not in result.evidence_flags


def test_complete_grading_is_not_flagged():
    listing = make_listing(
        '2024 Panini Prizm Joe Burrow Silver #55 PSA 10'
    )
    result = assess_underdescription(listing)

    assert 'GRADE_LABEL_INCOMPLETE' not in result.signal_codes
    assert 'GRADING_SPECIFIED' in result.evidence_flags


def test_no_identity_is_maximum_risk():
    listing = Listing(
        source='Test Store',
        external_id='test-2',
        url='https://example.com/test-2',
        title='Mystery Card',
        sport='NFL',
        price=10.0,
        identity=None,
    )

    result = assess_underdescription(listing)

    assert result.status == 'POOR_IDENTITY'
    assert result.risk_score == 100.0
    assert result.signal_codes == ('MISSING_IDENTITY',)

def test_comp_quality_below_sold_threshold_can_still_be_clear():
    listing = make_listing(
        '2024 Panini Prizm Joe Burrow'
    )
    result = assess_underdescription(listing)

    assert result.identity_quality == 0.55
    assert result.status == 'CLEAR'
    assert result.risk_score == 0.0
    assert 'LOW_IDENTITY_SPECIFICITY' not in result.signal_codes
    assert 'VERY_LOW_IDENTITY_SPECIFICITY' not in result.signal_codes


def test_sealed_box_is_not_applicable_to_card_underdescription():
    listing = make_listing(
        '2025 NFL Panini Absolute Football Sealed Bundle Box'
    )
    result = assess_underdescription(listing)

    assert result.status == 'NOT_APPLICABLE'
    assert result.risk_score == 0.0
    assert result.signal_codes == ()
    assert result.evidence_flags == ('NON_CARD_PRODUCT',)


def test_repack_product_is_not_applicable_to_card_underdescription():
    listing = make_listing(
        '2023 Gimko Hot Slab Pack AFL Series 1',
        sport='AFL',
    )
    result = assess_underdescription(listing)

    assert result.status == 'NOT_APPLICABLE'
    assert result.risk_score == 0.0
    assert result.signal_codes == ()
    assert 'NON_CARD_PRODUCT' in result.evidence_flags
