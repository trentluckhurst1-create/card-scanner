from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    db_path: str = os.getenv("CARD_SCANNER_DB", "data/card_scanner.sqlite3")
    ebay_client_id: str = os.getenv("EBAY_CLIENT_ID", "")
    ebay_client_secret: str = os.getenv("EBAY_CLIENT_SECRET", "")
    ebay_marketplace_id: str = os.getenv("EBAY_MARKETPLACE_ID", "EBAY_AU")
    min_opportunity_score: float = float(os.getenv("MIN_OPPORTUNITY_SCORE", "75"))
    market_cache_hours: float = float(os.getenv("MARKET_CACHE_HOURS", "6"))
    max_market_queries_per_run: int = int(os.getenv("MAX_MARKET_QUERIES_PER_RUN", "25"))
    ebay_results_per_query: int = int(os.getenv("EBAY_RESULTS_PER_QUERY", "25"))
    cherry_page_size: int = int(os.getenv("CHERRY_PAGE_SIZE", "250"))
    cherry_max_products_per_sport: int = int(os.getenv("CHERRY_MAX_PRODUCTS_PER_SPORT", "5000"))
    cherry_scan_cache_minutes: float = float(os.getenv("CHERRY_SCAN_CACHE_MINUTES", "30"))
    cherry_missing_scan_threshold: int = int(os.getenv("CHERRY_MISSING_SCAN_THRESHOLD", "3"))
    exact_comp_max_age_days: int = int(os.getenv("EXACT_COMP_MAX_AGE_DAYS", "365"))
    related_comp_max_age_days: int = int(os.getenv("RELATED_COMP_MAX_AGE_DAYS", "180"))
    min_exact_comps_high_confidence: int = int(os.getenv("MIN_EXACT_COMPS_HIGH_CONFIDENCE", "3"))
    min_total_comps_medium_confidence: int = int(os.getenv("MIN_TOTAL_COMPS_MEDIUM_CONFIDENCE", "3"))
    outlier_iqr_multiplier: float = float(os.getenv("OUTLIER_IQR_MULTIPLIER", "1.5"))
    quick_sale_discount: float = float(os.getenv("QUICK_SALE_DISCOUNT", "0.85"))
    opportunity_min_identity_confidence: float = float(os.getenv("OPPORTUNITY_MIN_IDENTITY_CONFIDENCE", "0.70"))
    opportunity_min_comp_confidence: float = float(os.getenv("OPPORTUNITY_MIN_COMP_CONFIDENCE", "0.55"))
    opportunity_buy_edge_pct: float = float(os.getenv("OPPORTUNITY_BUY_EDGE_PCT", "25"))
    opportunity_strong_buy_edge_pct: float = float(os.getenv("OPPORTUNITY_STRONG_BUY_EDGE_PCT", "45"))
    cherry_shipping_aud: str = os.getenv("CHERRY_SHIPPING_AUD", "")
    the_card_api_key: str = os.getenv("THE_CARD_API_KEY", "")
    the_card_api_base_url: str = os.getenv(
        "THE_CARD_API_BASE_URL",
        "https://thecardapi.com/api/v1/market/sales",
    )
    the_card_api_results_per_query: int = int(
        os.getenv("THE_CARD_API_RESULTS_PER_QUERY", "100")
    )
    the_card_api_recent_days: int = int(
        os.getenv("THE_CARD_API_RECENT_DAYS", "3")
    )

settings = Settings()
