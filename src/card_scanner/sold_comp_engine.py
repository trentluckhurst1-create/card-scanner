from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .comp_key import broad_comp_query, comp_quality, exact_comp_query
from .config import settings
from .market_matching import _same, _same_year, assess_match
from .models import (
    CardIdentity,
    MatchLevel,
    SoldComp,
    SoldCompMatch,
    SoldValuation,
)
from .providers import SoldCompProvider
from .risk import title_risk_flags
from .the_card_api import TheCardApiSoldCompProvider
from .valuation import value_from_sold_comps


MIN_SOLD_COMP_IDENTITY_QUALITY = 0.70


def player_recall_query(identity: CardIdentity) -> str | None:
    """
    High-recall API discovery query.

    Precision does NOT belong in the remote query. The provider should
    retrieve a broad player candidate pool and assess_strict_sold_comp()
    decides locally which sales are genuine valuation evidence.
    """

    if not identity.player:
        return None

    query = " ".join(identity.player.split()).strip()

    return query or None


@dataclass(frozen=True)
class EphemeralSoldCompScanResult:
    source_listing_external_id: str
    sport: str
    exact_query: str | None
    broad_query: str | None
    player_query: str | None
    identity_quality: float
    fetched_count: int
    accepted_count: int
    exact_count: int
    strong_count: int
    rejected_count: int
    query_count: int
    comp_matches: list[tuple[SoldComp, SoldCompMatch]]
    valuation: SoldValuation
    persistence_allowed: bool = False


def _reject(
    source_listing_external_id: str,
    comp: SoldComp,
    reasons: list[str],
) -> SoldCompMatch:
    return SoldCompMatch(
        source_listing_external_id=source_listing_external_id,
        sold_source=comp.source,
        sale_id=comp.sale_id,
        match_level=MatchLevel.REJECT,
        match_score=0.0,
        match_reasons=[],
        rejection_reasons=reasons,
    )


def assess_strict_sold_comp(
    source_listing_external_id: str,
    source: CardIdentity,
    comp: SoldComp,
) -> SoldCompMatch:
    candidate = comp.identity

    if candidate is None:
        return _reject(
            source_listing_external_id,
            comp,
            ["candidate identity missing"],
        )

    risks = title_risk_flags(comp.title)
    base = assess_match(source, candidate, risks)

    if base.match_level == MatchLevel.REJECT:
        return SoldCompMatch(
            source_listing_external_id=source_listing_external_id,
            sold_source=comp.source,
            sale_id=comp.sale_id,
            match_level=MatchLevel.REJECT,
            match_score=0.0,
            match_reasons=base.match_reasons,
            rejection_reasons=base.rejection_reasons,
        )

    strict_rejections: list[str] = []

    # Player is mandatory for target cards that have one.
    if source.player:
        if not candidate.player:
            strict_rejections.append("candidate player missing")
        elif not _same(source.player, candidate.player):
            strict_rejections.append("different player")

    # Year must be present and equal.
    if source.year:
        if not candidate.year:
            strict_rejections.append("candidate year missing")
        elif not _same_year(source.year, candidate.year):
            strict_rejections.append("different year")

    # Require set/brand identity rather than merely using it as a score.
    source_product = source.set_name or source.brand
    candidate_product = candidate.set_name or candidate.brand

    if source_product:
        if not candidate_product:
            strict_rejections.append("candidate set/brand missing")
        elif not _same(source_product, candidate_product):
            strict_rejections.append(
                f"different set/brand: "
                f"{source_product} vs {candidate_product}"
            )

    # Parallel must align exactly when the target identifies one.
    if source.parallel:
        if not candidate.parallel:
            strict_rejections.append("candidate parallel missing")
        elif not _same(source.parallel, candidate.parallel):
            strict_rejections.append("different parallel")

    # Numbered target requires the same print-run denominator.
    if source.serial_total is not None:
        if candidate.serial_total is None:
            strict_rejections.append(
                "candidate serial denominator missing"
            )
        elif source.serial_total != candidate.serial_total:
            strict_rejections.append(
                f"different serial denominator: "
                f"/{source.serial_total} vs /{candidate.serial_total}"
            )
    elif candidate.serial_total is not None:
        # Avoid substituting a numbered sibling for an unnumbered target.
        strict_rejections.append(
            "candidate is numbered but target is unnumbered"
        )

    # Serial numerator intentionally does NOT matter.

    # Card number mismatch is rejecting when both titles identify it.
    if (
        source.card_number
        and candidate.card_number
        and not _same(source.card_number, candidate.card_number)
    ):
        strict_rejections.append(
            f"different card number: "
            f"{source.card_number} vs {candidate.card_number}"
        )

    # Feature identity must align.
    if source.rookie != candidate.rookie:
        strict_rejections.append("rookie/1st status mismatch")

    if source.autograph != candidate.autograph:
        strict_rejections.append("autograph status mismatch")

    if source.memorabilia != candidate.memorabilia:
        strict_rejections.append("memorabilia status mismatch")

    source_graded = bool(
        source.grader or source.grade is not None
    )
    candidate_graded = bool(
        candidate.grader or candidate.grade is not None
    )

    if source_graded != candidate_graded:
        strict_rejections.append("raw vs graded mismatch")

    if source.grader:
        if not candidate.grader:
            strict_rejections.append("candidate grader missing")
        elif not _same(source.grader, candidate.grader):
            strict_rejections.append("different grader")

    if source.grade is not None:
        if candidate.grade is None:
            strict_rejections.append("candidate grade missing")
        elif float(source.grade) != float(candidate.grade):
            strict_rejections.append(
                f"different grade: "
                f"{source.grade:g} vs {candidate.grade:g}"
            )

    if strict_rejections:
        return _reject(
            source_listing_external_id,
            comp,
            strict_rejections,
        )

    # For sold comps we only permit EXACT/STRONG into valuation.
    # RELATED is audit evidence, not valuation evidence.
    if base.match_level not in {
        MatchLevel.EXACT,
        MatchLevel.STRONG,
    }:
        return _reject(
            source_listing_external_id,
            comp,
            ["strict sold-comp score below STRONG threshold"],
        )

    return SoldCompMatch(
        source_listing_external_id=source_listing_external_id,
        sold_source=comp.source,
        sale_id=comp.sale_id,
        match_level=base.match_level,
        match_score=base.match_score,
        match_reasons=base.match_reasons,
        rejection_reasons=[],
    )


class EphemeralSoldCompEngine:
    """
    Retrieves and values sold comps entirely in memory.

    API sales and matches are NEVER inserted into scanner SQLite tables.
    """

    persistence_allowed = False

    def __init__(
        self,
        provider: SoldCompProvider | None = None,
        results_per_query: int | None = None,
        recent_days: int | None = None,
    ):
        self.provider = provider or TheCardApiSoldCompProvider()
        self.results_per_query = int(
            settings.the_card_api_results_per_query
            if results_per_query is None
            else results_per_query
        )
        self.recent_days = int(
            settings.the_card_api_recent_days
            if recent_days is None
            else recent_days
        )

    @staticmethod
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

    def _recent(
        self,
        comps: list[SoldComp],
        as_of: date,
    ) -> list[SoldComp]:
        result: list[SoldComp] = []

        for comp in comps:
            try:
                sold = date.fromisoformat(comp.sold_date)
            except ValueError:
                continue

            age = (as_of - sold).days

            if 0 <= age <= self.recent_days:
                result.append(comp)

        return result

    def scan_identity(
        self,
        source_listing_external_id: str,
        sport: str,
        identity: CardIdentity,
        as_of: date | None = None,
    ) -> EphemeralSoldCompScanResult:
        as_of = as_of or date.today()
        sport = sport.upper()

        quality = comp_quality(identity)
        exact_query = exact_comp_query(identity)
        broad_query = broad_comp_query(identity)
        player_query = player_recall_query(identity)

        if quality < MIN_SOLD_COMP_IDENTITY_QUALITY:
            valuation = SoldValuation(
                source_listing_external_id=(
                    source_listing_external_id
                ),
                status="INSUFFICIENT_IDENTITY",
                explanation={
                    "reason": "identity quality below sold-comp threshold",
                    "persistence_allowed": False,
                },
            )

            return EphemeralSoldCompScanResult(
                source_listing_external_id=(
                    source_listing_external_id
                ),
                sport=sport,
                exact_query=exact_query,
                broad_query=broad_query,
                player_query=player_query,
                identity_quality=quality,
                fetched_count=0,
                accepted_count=0,
                exact_count=0,
                strong_count=0,
                rejected_count=0,
                query_count=0,
                comp_matches=[],
                valuation=valuation,
            )

        all_comps: list[SoldComp] = []
        queries_used = 0

        # High-recall discovery: retrieve by player first.
        #
        # Do not put year/set/parallel/serial/grade precision into the
        # primary API query. Real marketplace titles vary too much and
        # rare-card terms can collapse remote recall to zero.
        #
        # Precision remains entirely governed by
        # assess_strict_sold_comp().
        if player_query:
            all_comps.extend(
                self.provider.sold_comps(
                    sport,
                    player_query,
                    self.results_per_query,
                )
            )
            queries_used += 1

        all_comps = self._dedupe(all_comps)
        recent = self._recent(all_comps, as_of)

        assessed = [
            (
                comp,
                assess_strict_sold_comp(
                    source_listing_external_id,
                    identity,
                    comp,
                ),
            )
            for comp in recent
        ]

        accepted = [
            pair
            for pair in assessed
            if pair[1].match_level
            in {MatchLevel.EXACT, MatchLevel.STRONG}
        ]

        # Supplemental identity-aware retrieval is permitted only when
        # the player recall pool did not produce sufficient genuine
        # comps. Strict local matching remains unchanged.
        if (
            len(accepted)
            < settings.min_total_comps_medium_confidence
            and broad_query
            and broad_query != player_query
        ):
            all_comps.extend(
                self.provider.sold_comps(
                    sport,
                    broad_query,
                    self.results_per_query,
                )
            )
            queries_used += 1

            all_comps = self._dedupe(all_comps)
            recent = self._recent(all_comps, as_of)

            assessed = [
                (
                    comp,
                    assess_strict_sold_comp(
                        source_listing_external_id,
                        identity,
                        comp,
                    ),
                )
                for comp in recent
            ]

            accepted = [
                pair
                for pair in assessed
                if pair[1].match_level
                in {MatchLevel.EXACT, MatchLevel.STRONG}
            ]

        valuation = value_from_sold_comps(
            source_listing_external_id,
            accepted,
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
                        "recent_days": self.recent_days,
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
                        "recent_days": self.recent_days,
                        "persistence_allowed": False,
                    },
                }
            )

        exact_count = sum(
            1
            for _, match in accepted
            if match.match_level == MatchLevel.EXACT
        )
        strong_count = sum(
            1
            for _, match in accepted
            if match.match_level == MatchLevel.STRONG
        )
        rejected_count = sum(
            1
            for _, match in assessed
            if match.match_level == MatchLevel.REJECT
        )

        return EphemeralSoldCompScanResult(
            source_listing_external_id=source_listing_external_id,
            sport=sport,
            exact_query=exact_query,
            broad_query=broad_query,
            player_query=player_query,
            identity_quality=quality,
            fetched_count=len(recent),
            accepted_count=len(accepted),
            exact_count=exact_count,
            strong_count=strong_count,
            rejected_count=rejected_count,
            query_count=queries_used,
            comp_matches=accepted,
            valuation=valuation,
        )
