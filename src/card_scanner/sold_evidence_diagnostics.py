from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from statistics import median

from .comp_key import broad_comp_query, comp_quality, exact_comp_query
from .config import settings
from .market_matching import _norm, _same, _same_year
from .models import (
    CardIdentity,
    Listing,
    MatchLevel,
    SoldComp,
    SoldCompMatch,
    SoldValuation,
)
from .opportunity_scanner import (
    MultiStoreSource,
    SPORTS,
    StoreSearchSource,
    candidate_priority,
)
from .risk import title_risk_flags
from .sold_comp_engine import (
    MIN_SOLD_COMP_IDENTITY_QUALITY,
    assess_strict_sold_comp,
    player_recall_query,
)
from .valuation import value_from_sold_comps


FUNNEL_STAGES = (
    "API_ROWS",
    "UNIQUE_ROWS",
    "IDENTITY_PARSED",
    "SAME_PLAYER",
    "SAME_YEAR",
    "SAME_PRODUCT",
    "SAME_CARD_NUMBER",
    "SAME_PARALLEL",
    "SAME_SERIAL",
    "SAME_ROOKIE",
    "SAME_AUTO_MEM",
    "SAME_GRADING",
    "EXACT",
    "STRONG",
    "ACCEPTED",
    "VALUED",
)


BOTTLENECK_BUCKETS = (
    "NO_SALES_RETURNED",
    "PLAYER_RESULTS_BUT_WRONG_YEAR",
    "WRONG_PRODUCT",
    "WRONG_CARD_NUMBER",
    "WRONG_PARALLEL",
    "WRONG_SERIAL",
    "ROOKIE_MISMATCH",
    "AUTO_MEM_MISMATCH",
    "GRADING_MISMATCH",
    "IDENTITY_PARSE_FAILURE",
    "INSUFFICIENT_EXACT_COMPS",
    "PRICE_DISPERSION",
    "RECENCY",
    "QUERY_DISCOVERY_FAILURE",
    "OTHER",
)


@dataclass(frozen=True)
class SoldEvidenceQueryDiagnostic:
    query_text: str
    rows_returned: int


@dataclass(frozen=True)
class SoldEvidenceRejectionExample:
    sale_id: str
    title: str
    sold_date: str
    price: float
    currency: str
    sold_price_aud: float | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SoldEvidenceAcceptedCompDiagnostic:
    sale_id: str
    title: str
    sold_date: str
    price: float
    currency: str
    sold_price_aud: float | None
    sale_type: str | None
    match_level: str
    match_score: float
    match_reasons: tuple[str, ...]
    identity_summary: str


@dataclass(frozen=True)
class SoldEvidenceCandidateDiagnostic:
    source: str
    external_id: str
    sport: str
    listing_title: str
    parsed_identity: CardIdentity | None
    identity_summary: str
    identity_quality: float
    exact_query: str | None
    broad_query: str | None
    player_query: str | None
    queries: tuple[SoldEvidenceQueryDiagnostic, ...]
    unique_sold_rows: int
    rows_with_parseable_identity: int
    recent_sold_rows: int
    exact_matches: int
    strong_matches: int
    rejected_matches: int
    rejection_reason_counts: dict[str, int]
    sale_dates: tuple[str, ...]
    sale_ages_days: tuple[int | None, ...]
    prices: tuple[float, ...]
    currencies: tuple[str, ...]
    aud_prices: tuple[float | None, ...]
    median_aud: float | None
    spread_pct: float | None
    median_absolute_deviation_pct: float | None
    valuation_status: str
    valuation_confidence: float
    query_count: int
    funnel: dict[str, int]
    bottleneck_counts: dict[str, int]
    accepted_comps: tuple[SoldEvidenceAcceptedCompDiagnostic, ...]
    rejected_examples: tuple[SoldEvidenceRejectionExample, ...]
    valuation: SoldValuation
    persistence_allowed: bool = False


@dataclass(frozen=True)
class SoldEvidenceDiagnosticSummary:
    results: tuple[SoldEvidenceCandidateDiagnostic, ...]
    fetched_listings: int
    candidates_considered: int
    candidates_scanned: int
    sold_api_calls: int
    query_budget: int
    budget_remaining: int
    valued_count: int
    aggregate_funnel: dict[str, int]
    bottleneck_counts: dict[str, int]
    store_errors: tuple[str, ...] = ()
    persistence_writes: int = 0
    history_writes: int = 0
    raw_api_persistence: bool = False


def _identity_summary(identity: CardIdentity | None) -> str:
    if identity is None:
        return ""

    fields = [
        identity.sport,
        identity.year,
        identity.set_name or identity.brand,
        identity.player,
        f"#{identity.card_number}" if identity.card_number else None,
        identity.parallel,
        f"/{identity.serial_total}" if identity.serial_total else None,
        "RC" if identity.rookie else None,
        "AUTO" if identity.autograph else None,
        "MEM" if identity.memorabilia else None,
        identity.grader,
        (
            f"{identity.grade:g}"
            if identity.grade is not None
            else None
        ),
    ]

    return " | ".join(str(field) for field in fields if field)


def _dedupe(comps: list[SoldComp]) -> list[SoldComp]:
    seen: set[tuple[str, str]] = set()
    result: list[SoldComp] = []

    for comp in comps:
        key = (comp.source, comp.sale_id)

        if key in seen:
            continue

        seen.add(key)
        result.append(comp)

    return result


def _age_days(comp: SoldComp, as_of: date) -> int | None:
    try:
        sold = date.fromisoformat(comp.sold_date)
    except ValueError:
        return None

    return (as_of - sold).days


def _recent(
    comps: list[SoldComp],
    as_of: date,
    recent_days: int,
) -> list[SoldComp]:
    result: list[SoldComp] = []

    for comp in comps:
        age = _age_days(comp, as_of)

        if age is not None and 0 <= age <= recent_days:
            result.append(comp)

    return result


def _price_spread_pct(values: list[float]) -> float | None:
    if not values:
        return None

    baseline = median(values)

    if baseline <= 0:
        return None

    return round((max(values) - min(values)) / baseline * 100.0, 2)


def _median_absolute_deviation_pct(values: list[float]) -> float | None:
    if not values:
        return None

    baseline = median(values)

    if baseline <= 0:
        return None

    deviations = [abs(value - baseline) for value in values]

    return round(median(deviations) / baseline * 100.0, 2)


def _has_grading(identity: CardIdentity) -> bool:
    return bool(identity.grader or identity.grade is not None)


def _same_product(
    source: CardIdentity,
    candidate: CardIdentity,
) -> bool:
    source_product = source.set_name or source.brand
    candidate_product = candidate.set_name or candidate.brand

    return bool(
        source_product
        and candidate_product
        and _same(source_product, candidate_product)
    )


def build_sold_evidence_funnel(
    source_listing_external_id: str,
    source: CardIdentity,
    comps: list[SoldComp],
) -> dict[str, int]:
    """
    Reporting-only cumulative sold-evidence identity funnel.

    Counts explain where candidate sale rows fall away. This function
    does not accept comps, value cards, or alter production decisions.
    """
    counts = {stage: 0 for stage in FUNNEL_STAGES}
    unique = _dedupe(comps)

    counts["API_ROWS"] = len(comps)
    counts["UNIQUE_ROWS"] = len(unique)

    for comp in unique:
        candidate = comp.identity

        if candidate is None:
            continue
        counts["IDENTITY_PARSED"] += 1

        if not source.player or not candidate.player:
            continue
        if _norm(source.player) != _norm(candidate.player):
            continue
        counts["SAME_PLAYER"] += 1

        if source.year:
            if not candidate.year or not _same_year(source.year, candidate.year):
                continue
        counts["SAME_YEAR"] += 1

        if source.set_name or source.brand:
            if not _same_product(source, candidate):
                continue
        counts["SAME_PRODUCT"] += 1

        if source.card_number:
            if not candidate.card_number or not _same(
                source.card_number,
                candidate.card_number,
            ):
                continue
        counts["SAME_CARD_NUMBER"] += 1

        if source.parallel:
            if not candidate.parallel or not _same(
                source.parallel,
                candidate.parallel,
            ):
                continue
        elif candidate.parallel:
            continue
        counts["SAME_PARALLEL"] += 1

        if source.serial_total is not None:
            if candidate.serial_total != source.serial_total:
                continue
        elif candidate.serial_total is not None:
            continue
        counts["SAME_SERIAL"] += 1

        if source.rookie != candidate.rookie:
            continue
        counts["SAME_ROOKIE"] += 1

        if (
            source.autograph != candidate.autograph
            or source.memorabilia != candidate.memorabilia
        ):
            continue
        counts["SAME_AUTO_MEM"] += 1

        if _has_grading(source) != _has_grading(candidate):
            continue
        if source.grader:
            if not candidate.grader or not _same(source.grader, candidate.grader):
                continue
        if source.grade is not None:
            if candidate.grade is None:
                continue
            if float(source.grade) != float(candidate.grade):
                continue
        counts["SAME_GRADING"] += 1

        match = assess_strict_sold_comp(
            source_listing_external_id,
            source,
            comp,
        )

        if match.match_level == MatchLevel.EXACT:
            counts["EXACT"] += 1
        elif match.match_level == MatchLevel.STRONG:
            counts["STRONG"] += 1

    return counts


def _map_rejection_reason(reason: str) -> str:
    if reason.startswith("candidate identity"):
        return "IDENTITY_PARSE_FAILURE"
    if reason.startswith(("candidate year", "different year")):
        return "PLAYER_RESULTS_BUT_WRONG_YEAR"
    if reason.startswith(("candidate set/brand", "different set/brand")):
        return "WRONG_PRODUCT"
    if reason.startswith("different card number"):
        return "WRONG_CARD_NUMBER"
    if reason.startswith(("candidate parallel", "different parallel")):
        return "WRONG_PARALLEL"
    if reason.startswith(("candidate serial", "different serial")):
        return "WRONG_SERIAL"
    if reason.startswith("candidate is numbered"):
        return "WRONG_SERIAL"
    if reason.startswith("rookie/1st"):
        return "ROOKIE_MISMATCH"
    if reason.startswith(("autograph", "memorabilia")):
        return "AUTO_MEM_MISMATCH"
    if reason.startswith(
        (
            "raw vs graded",
            "candidate grader",
            "different grader",
            "candidate grade",
            "different grade",
        )
    ):
        return "GRADING_MISMATCH"
    if reason.startswith("strict sold-comp score"):
        return "QUERY_DISCOVERY_FAILURE"

    return "OTHER"


def _bottlenecks(
    comps: list[SoldComp],
    recent: list[SoldComp],
    assessed_recent: list[tuple[SoldComp, SoldCompMatch]],
    accepted_recent: list[tuple[SoldComp, SoldCompMatch]],
    valuation: SoldValuation,
    as_of: date,
    recent_days: int,
) -> dict[str, int]:
    counts: Counter[str] = Counter()

    if not comps:
        counts["NO_SALES_RETURNED"] += 1

    if comps and not any(comp.identity is not None for comp in comps):
        counts["IDENTITY_PARSE_FAILURE"] += 1

    stale_or_future = 0
    for comp in comps:
        age = _age_days(comp, as_of)
        if age is None or age < 0 or age > recent_days:
            stale_or_future += 1
    if stale_or_future:
        counts["RECENCY"] += stale_or_future

    for _, match in assessed_recent:
        for reason in match.rejection_reasons:
            counts[_map_rejection_reason(reason)] += 1

    if (
        comps
        and recent
        and not accepted_recent
        and not any(
            bucket in counts
            for bucket in BOTTLENECK_BUCKETS
            if bucket != "OTHER"
        )
    ):
        counts["OTHER"] += 1

    if (
        accepted_recent
        and len(accepted_recent)
        < settings.min_total_comps_medium_confidence
    ):
        counts["INSUFFICIENT_EXACT_COMPS"] += 1

    spread = valuation.explanation.get("price_spread_pct")
    if isinstance(spread, (int, float)) and spread >= 60.0:
        counts["PRICE_DISPERSION"] += 1

    return {
        bucket: int(counts.get(bucket, 0))
        for bucket in BOTTLENECK_BUCKETS
        if counts.get(bucket, 0)
    }


def _accepted_diagnostic(
    comp: SoldComp,
    match: SoldCompMatch,
) -> SoldEvidenceAcceptedCompDiagnostic:
    return SoldEvidenceAcceptedCompDiagnostic(
        sale_id=comp.sale_id,
        title=comp.title,
        sold_date=comp.sold_date,
        price=comp.sold_price,
        currency=comp.currency,
        sold_price_aud=comp.sold_price_aud,
        sale_type=comp.sale_type,
        match_level=match.match_level.value,
        match_score=match.match_score,
        match_reasons=tuple(match.match_reasons),
        identity_summary=_identity_summary(comp.identity),
    )


def _rejection_example(
    comp: SoldComp,
    match: SoldCompMatch,
) -> SoldEvidenceRejectionExample:
    return SoldEvidenceRejectionExample(
        sale_id=comp.sale_id,
        title=comp.title,
        sold_date=comp.sold_date,
        price=comp.sold_price,
        currency=comp.currency,
        sold_price_aud=comp.sold_price_aud,
        reasons=tuple(match.rejection_reasons),
    )


def diagnose_sold_evidence_candidate(
    listing: Listing,
    sold_provider,
    *,
    sold_results_per_query: int | None = None,
    max_queries: int = 2,
    recent_days: int | None = None,
    as_of: date | None = None,
) -> SoldEvidenceCandidateDiagnostic:
    as_of = as_of or date.today()
    recent_days = (
        settings.the_card_api_recent_days
        if recent_days is None
        else int(recent_days)
    )
    limit = int(
        settings.the_card_api_results_per_query
        if sold_results_per_query is None
        else sold_results_per_query
    )
    max_queries = max(0, min(int(max_queries), 2))
    identity = listing.identity
    quality = comp_quality(identity) if identity else 0.0
    exact_query = exact_comp_query(identity) if identity else None
    broad_query = broad_comp_query(identity) if identity else None
    player_query = player_recall_query(identity) if identity else None
    all_comps: list[SoldComp] = []
    queries: list[SoldEvidenceQueryDiagnostic] = []

    if identity is None or quality < MIN_SOLD_COMP_IDENTITY_QUALITY:
        valuation = SoldValuation(
            source_listing_external_id=listing.external_id,
            status="INSUFFICIENT_IDENTITY",
            explanation={
                "reason": "identity quality below sold-comp threshold",
                "persistence_allowed": False,
            },
        )
        return SoldEvidenceCandidateDiagnostic(
            source=listing.source,
            external_id=listing.external_id,
            sport=listing.sport.upper(),
            listing_title=listing.title,
            parsed_identity=identity,
            identity_summary=_identity_summary(identity),
            identity_quality=quality,
            exact_query=exact_query,
            broad_query=broad_query,
            player_query=player_query,
            queries=(),
            unique_sold_rows=0,
            rows_with_parseable_identity=0,
            recent_sold_rows=0,
            exact_matches=0,
            strong_matches=0,
            rejected_matches=0,
            rejection_reason_counts={},
            sale_dates=(),
            sale_ages_days=(),
            prices=(),
            currencies=(),
            aud_prices=(),
            median_aud=None,
            spread_pct=None,
            median_absolute_deviation_pct=None,
            valuation_status=valuation.status,
            valuation_confidence=0.0,
            query_count=0,
            funnel={stage: 0 for stage in FUNNEL_STAGES},
            bottleneck_counts={"IDENTITY_PARSE_FAILURE": 1},
            accepted_comps=(),
            rejected_examples=(),
            valuation=valuation,
        )

    def run_query(query_text: str | None) -> None:
        if not query_text:
            return
        rows = sold_provider.sold_comps(
            listing.sport.upper(),
            query_text,
            limit,
        )
        all_comps.extend(rows)
        queries.append(
            SoldEvidenceQueryDiagnostic(
                query_text=query_text,
                rows_returned=len(rows),
            )
        )

    if player_query and len(queries) < max_queries:
        run_query(player_query)

    unique = _dedupe(all_comps)
    recent = _recent(unique, as_of, recent_days)
    assessed_recent = [
        (
            comp,
            assess_strict_sold_comp(
                listing.external_id,
                identity,
                comp,
            ),
        )
        for comp in recent
    ]
    accepted_recent = [
        pair
        for pair in assessed_recent
        if pair[1].match_level in {MatchLevel.EXACT, MatchLevel.STRONG}
    ]

    if (
        len(accepted_recent) < settings.min_total_comps_medium_confidence
        and broad_query
        and broad_query != player_query
        and len(queries) < max_queries
    ):
        run_query(broad_query)
        unique = _dedupe(all_comps)
        recent = _recent(unique, as_of, recent_days)
        assessed_recent = [
            (
                comp,
                assess_strict_sold_comp(
                    listing.external_id,
                    identity,
                    comp,
                ),
            )
            for comp in recent
        ]
        accepted_recent = [
            pair
            for pair in assessed_recent
            if pair[1].match_level in {MatchLevel.EXACT, MatchLevel.STRONG}
        ]

    valuation = value_from_sold_comps(
        listing.external_id,
        accepted_recent,
        as_of=as_of,
    )
    if valuation.status != "VALUED":
        valuation = valuation.model_copy(
            update={
                "status": "INSUFFICIENT_RECENT_COMPS",
                "explanation": {
                    **valuation.explanation,
                    "reason": (
                        "free-tier 3-day player-recall exact/strong "
                        "sold-comp depth insufficient"
                    ),
                    "recent_days": recent_days,
                    "persistence_allowed": False,
                },
            }
        )
    else:
        valuation = valuation.model_copy(
            update={
                "explanation": {
                    **valuation.explanation,
                    "source": "the_card_api_ephemeral",
                    "recent_days": recent_days,
                    "persistence_allowed": False,
                },
            }
        )

    funnel = build_sold_evidence_funnel(
        listing.external_id,
        identity,
        all_comps,
    )
    funnel["ACCEPTED"] = len(accepted_recent)
    funnel["VALUED"] = 1 if valuation.status == "VALUED" else 0

    rejection_counts: Counter[str] = Counter()
    for _, match in assessed_recent:
        rejection_counts.update(match.rejection_reasons)

    aud_values = [
        float(comp.sold_price_aud)
        for comp, _ in accepted_recent
        if comp.sold_price_aud is not None and comp.sold_price_aud > 0
    ]
    sale_ages = tuple(_age_days(comp, as_of) for comp in unique)
    prices = tuple(float(comp.sold_price) for comp in unique)
    currencies = tuple(comp.currency for comp in unique)
    aud_prices = tuple(comp.sold_price_aud for comp in unique)

    rejected = [
        pair
        for pair in assessed_recent
        if pair[1].match_level == MatchLevel.REJECT
    ]

    return SoldEvidenceCandidateDiagnostic(
        source=listing.source,
        external_id=listing.external_id,
        sport=listing.sport.upper(),
        listing_title=listing.title,
        parsed_identity=identity,
        identity_summary=_identity_summary(identity),
        identity_quality=quality,
        exact_query=exact_query,
        broad_query=broad_query,
        player_query=player_query,
        queries=tuple(queries),
        unique_sold_rows=len(unique),
        rows_with_parseable_identity=sum(
            1
            for comp in unique
            if comp.identity is not None
        ),
        recent_sold_rows=len(recent),
        exact_matches=sum(
            1
            for _, match in assessed_recent
            if match.match_level == MatchLevel.EXACT
        ),
        strong_matches=sum(
            1
            for _, match in assessed_recent
            if match.match_level == MatchLevel.STRONG
        ),
        rejected_matches=sum(
            1
            for _, match in assessed_recent
            if match.match_level == MatchLevel.REJECT
        ),
        rejection_reason_counts=dict(sorted(rejection_counts.items())),
        sale_dates=tuple(comp.sold_date for comp in unique),
        sale_ages_days=sale_ages,
        prices=prices,
        currencies=currencies,
        aud_prices=aud_prices,
        median_aud=round(median(aud_values), 2) if aud_values else None,
        spread_pct=_price_spread_pct(aud_values),
        median_absolute_deviation_pct=(
            _median_absolute_deviation_pct(aud_values)
        ),
        valuation_status=valuation.status,
        valuation_confidence=valuation.comp_confidence,
        query_count=len(queries),
        funnel=funnel,
        bottleneck_counts=_bottlenecks(
            unique,
            recent,
            assessed_recent,
            accepted_recent,
            valuation,
            as_of,
            recent_days,
        ),
        accepted_comps=tuple(
            _accepted_diagnostic(comp, match)
            for comp, match in accepted_recent
        ),
        rejected_examples=tuple(
            _rejection_example(comp, match)
            for comp, match in rejected[:5]
        ),
        valuation=valuation,
    )


def scan_store_sold_evidence_diagnostics(
    store_source: StoreSearchSource,
    sold_provider,
    *,
    sport: str = "ALL",
    listings_per_sport: int = 50,
    max_candidates_per_sport: int = 10,
    sold_results_per_query: int = 100,
    max_sold_queries: int = 8,
    as_of: date | None = None,
) -> SoldEvidenceDiagnosticSummary:
    as_of = as_of or date.today()
    sport = sport.upper()

    if sport == "ALL":
        sports = list(SPORTS)
    elif sport in SPORTS:
        sports = [sport]
    else:
        raise ValueError(
            f"Unsupported sport: {sport}. "
            "Expected NFL, NBA, MLB, AFL or ALL."
        )

    fetched_listings = 0
    candidates_considered = 0
    candidates_scanned = 0
    sold_api_calls = 0
    results: list[SoldEvidenceCandidateDiagnostic] = []
    store_errors: list[str] = []

    for sport_name in sports:
        if sold_api_calls >= max_sold_queries:
            break

        if isinstance(store_source, MultiStoreSource):
            collection = store_source.collect(
                sport_name,
                "",
                listings_per_sport,
            )
            listings = collection.listings
            store_errors.extend(collection.store_errors)
        else:
            listings = store_source.search(
                sport_name,
                "",
                listings_per_sport,
            )

        fetched_listings += len(listings)
        eligible = []

        for listing in sorted(listings, key=candidate_priority):
            identity = listing.identity
            quality = comp_quality(identity) if identity else 0.0

            if (
                identity is None
                or not identity.player
                or quality < MIN_SOLD_COMP_IDENTITY_QUALITY
            ):
                continue

            eligible.append(listing)

        selected = eligible[:max_candidates_per_sport]
        candidates_considered += len(selected)

        for listing in selected:
            remaining = max_sold_queries - sold_api_calls

            if remaining < 1:
                break

            diagnostic = diagnose_sold_evidence_candidate(
                listing,
                sold_provider,
                sold_results_per_query=sold_results_per_query,
                max_queries=min(2, remaining),
                as_of=as_of,
            )
            sold_api_calls += diagnostic.query_count
            candidates_scanned += 1
            results.append(diagnostic)

    aggregate_funnel = {stage: 0 for stage in FUNNEL_STAGES}
    bottlenecks: Counter[str] = Counter()

    for result in results:
        for stage in FUNNEL_STAGES:
            aggregate_funnel[stage] += result.funnel.get(stage, 0)
        bottlenecks.update(result.bottleneck_counts)

    return SoldEvidenceDiagnosticSummary(
        results=tuple(results),
        fetched_listings=fetched_listings,
        candidates_considered=candidates_considered,
        candidates_scanned=candidates_scanned,
        sold_api_calls=sold_api_calls,
        query_budget=max_sold_queries,
        budget_remaining=max_sold_queries - sold_api_calls,
        valued_count=sum(
            1
            for result in results
            if result.valuation_status == "VALUED"
        ),
        aggregate_funnel=aggregate_funnel,
        bottleneck_counts=dict(sorted(bottlenecks.items())),
        store_errors=tuple(store_errors),
    )
