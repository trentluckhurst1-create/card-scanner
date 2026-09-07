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

settings = Settings()
