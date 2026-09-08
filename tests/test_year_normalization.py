from card_scanner.comp_key import identity_signature
from card_scanner.identity import parse_identity
from card_scanner.market_matching import assess_match
from card_scanner.models import MatchLevel, SoldComp
from card_scanner.sold_comp_engine import assess_strict_sold_comp
from card_scanner.year_normalization import normalize_card_year


def test_normalize_card_year_keeps_single_and_season_years_distinct():
    assert normalize_card_year("2024") == "2024"
    assert normalize_card_year("2024-25") == "2024-2025"
    assert normalize_card_year("2024/25") == "2024-2025"
    assert normalize_card_year("1997-98") == "1997-1998"
    assert normalize_card_year("1999-00") == "1999-2000"
    assert normalize_card_year(None) is None
    assert normalize_card_year("") is None
    assert normalize_card_year("2024-26") is None


def test_season_year_variants_share_identity_signature():
    first = parse_identity(
        "2024-25 Panini Prizm Example Player Silver #10",
        "NBA",
    )
    second = parse_identity(
        "2024/25 Panini Prizm Example Player Silver #10",
        "NBA",
    )

    assert first.year == "2024-25"
    assert second.year == "2024/25"
    assert identity_signature(first) == identity_signature(second)


def test_single_year_and_season_year_signatures_do_not_match():
    single = parse_identity(
        "2024 Panini Prizm Example Player Silver #10",
        "NBA",
    )
    season = parse_identity(
        "2024-25 Panini Prizm Example Player Silver #10",
        "NBA",
    )

    assert identity_signature(single) != identity_signature(season)


def test_market_matching_accepts_hyphen_slash_season_equivalence():
    source = parse_identity(
        "2024-25 Panini Prizm Example Player Silver #10",
        "NBA",
    )
    candidate = parse_identity(
        "2024/25 Panini Prizm Example Player Silver #10",
        "NBA",
    )

    assert assess_match(source, candidate).match_level is MatchLevel.EXACT


def test_market_matching_rejects_single_year_vs_season_year():
    source = parse_identity(
        "2024 Panini Prizm Example Player Silver #10",
        "NBA",
    )
    candidate = parse_identity(
        "2024-25 Panini Prizm Example Player Silver #10",
        "NBA",
    )

    result = assess_match(source, candidate)

    assert result.match_level is MatchLevel.REJECT
    assert "different year: 2024 vs 2024-25" in result.rejection_reasons


def test_strict_sold_matching_uses_normalized_season_years():
    source = parse_identity(
        "2024-25 Panini Prizm Example Player Silver #10",
        "NBA",
    )
    comp = SoldComp(
        source="the_card_api_ebay",
        sale_id="sale-1",
        sold_date="2026-09-08",
        title="2024/25 Panini Prizm Example Player Silver #10",
        sold_price=100.0,
        currency="AUD",
        sold_price_aud=100.0,
        identity=parse_identity(
            "2024/25 Panini Prizm Example Player Silver #10",
            "NBA",
        ),
    )

    assert (
        assess_strict_sold_comp("listing-1", source, comp).match_level
        is MatchLevel.EXACT
    )
