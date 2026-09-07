from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

SUPPORTED_SPORTS = {"NFL", "NBA", "MLB", "AFL"}

class CardIdentity(BaseModel):
    sport: str
    year: Optional[str] = None
    brand: Optional[str] = None
    set_name: Optional[str] = None
    player: Optional[str] = None
    card_number: Optional[str] = None
    parallel: Optional[str] = None
    serial_current: Optional[int] = None
    serial_total: Optional[int] = None
    rookie: bool = False
    autograph: bool = False
    memorabilia: bool = False
    grader: Optional[str] = None
    grade: Optional[float] = None

class Listing(BaseModel):
    source: str
    external_id: str
    url: str
    title: str
    sport: str
    price: float
    currency: str = "AUD"
    shipping: float = 0.0
    image_url: Optional[str] = None
    seller: Optional[str] = None
    condition: Optional[str] = None
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    identity: Optional[CardIdentity] = None

class MatchLevel(str, Enum):
    EXACT = "EXACT"
    STRONG = "STRONG"
    RELATED = "RELATED"
    REJECT = "REJECT"

class MarketListing(BaseModel):
    source: str
    external_id: str
    title: str
    url: str
    price: float
    currency: str
    shipping: Optional[float] = None
    seller: Optional[str] = None
    condition: Optional[str] = None
    buying_option: Optional[str] = None
    image_url: Optional[str] = None
    marketplace: str = "EBAY_AU"
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    identity: Optional[CardIdentity] = None
    risk_flags: list[str] = Field(default_factory=list)
    landed_price_aud: Optional[float] = None
    fx_status: str = "FX_PENDING"

class MarketMatch(BaseModel):
    source_listing_external_id: str
    market_source: str
    market_external_id: str
    match_level: MatchLevel
    match_score: float
    match_reasons: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)

class ActiveMarketMetrics(BaseModel):
    source_listing_external_id: str
    active_match_count: int = 0
    active_exact_count: int = 0
    active_strong_count: int = 0
    active_lowest_aud: Optional[float] = None
    active_median_aud: Optional[float] = None
    active_trimmed_median_aud: Optional[float] = None
    active_mean_aud: Optional[float] = None
    active_max_aud: Optional[float] = None
    active_market_spread: Optional[float] = None
    cherry_vs_active_lowest_pct: Optional[float] = None
    cherry_vs_active_median_pct: Optional[float] = None
    market_match_confidence: float = 0.0
    status: str = "NO_MARKET_MATCHES"

class SoldComp(BaseModel):
    source: str
    sale_id: str
    sold_date: str
    title: str
    sold_price: float
    currency: str
    shipping: Optional[float] = None
    sold_price_aud: Optional[float] = None
    sale_type: Optional[str] = None
    url: Optional[str] = None
    notes: Optional[str] = None
    identity: Optional[CardIdentity] = None
    imported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SoldCompMatch(BaseModel):
    source_listing_external_id: str
    sold_source: str
    sale_id: str
    match_level: MatchLevel
    match_score: float
    match_reasons: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)

class IdentityAuditRow(BaseModel):
    external_id: str
    sport: str
    title: str
    identity: Optional[CardIdentity] = None
    confidence: float
    explanations: list[str] = Field(default_factory=list)

class SoldValuation(BaseModel):
    source_listing_external_id: str
    sold_comp_count: int = 0
    exact_comp_count: int = 0
    strong_comp_count: int = 0
    related_comp_count: int = 0
    latest_sale_aud: Optional[float] = None
    median_sale_aud: Optional[float] = None
    weighted_median_aud: Optional[float] = None
    trimmed_mean_aud: Optional[float] = None
    median_30_day_aud: Optional[float] = None
    median_90_day_aud: Optional[float] = None
    median_180_day_aud: Optional[float] = None
    fair_value_aud: Optional[float] = None
    quick_sale_value_aud: Optional[float] = None
    liquidity_score: float = 0.0
    comp_confidence: float = 0.0
    market_direction: str = "INSUFFICIENT_DATA"
    market_direction_reason: str = ""
    status: str = "INSUFFICIENT_SOLD_COMPS"
    explanation: dict = Field(default_factory=dict)

class Opportunity(BaseModel):
    source_listing_external_id: str
    landed_cost_aud: Optional[float] = None
    fair_value_aud: Optional[float] = None
    quick_sale_value_aud: Optional[float] = None
    edge_pct: Optional[float] = None
    opportunity_score: float = 0.0
    identity_confidence: float = 0.0
    comp_confidence: float = 0.0
    liquidity_score: float = 0.0
    risk_score: float = 0.0
    market_direction: str = "INSUFFICIENT_DATA"
    status: str = "INSUFFICIENT_SOLD_COMPS"
    reasons: list[str] = Field(default_factory=list)

class WatchItem(BaseModel):
    watch_type: str
    value: str
    sport: Optional[str] = None
    label: Optional[str] = None

class WatchEvent(BaseModel):
    watch_item_id: Optional[int] = None
    event_type: str
    source: Optional[str] = None
    external_id: Optional[str] = None
    details: dict = Field(default_factory=dict)

class RiskFlag(BaseModel):
    code: str
    severity: str
    reason: str

class Valuation(BaseModel):
    listing_external_id: str
    landed_cost_aud: float
    fair_value_aud: Optional[float] = None
    quick_sale_value_aud: Optional[float] = None
    comp_count: int = 0
    comp_confidence: float = 0.0
    liquidity: float = 0.0
    identity_confidence: float = 0.0
    risk_penalty: float = 0.0
    opportunity_score: float = 0.0
    edge_pct: Optional[float] = None
