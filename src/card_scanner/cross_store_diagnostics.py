from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .cross_store_reference import (
    _landed_aud,
    _same_known_card_number,
    _same_source,
    _same_source_item,
)
from .market_matching import _norm, assess_match
from .models import Listing, MatchLevel
from .risk import title_risk_flags
from .year_normalization import normalize_card_year


@dataclass(frozen=True)
class ReferenceRejectionDiagnostic:
    candidate_source: str
    candidate_external_id: str
    reference_source: str
    reference_external_id: str
    reasons: tuple[str, ...]
    match_level: str | None = None
    details: tuple[str, ...] = ()


def _add(
    reasons: list[str],
    reason: str,
) -> None:
    if reason not in reasons:
        reasons.append(reason)


def _map_match_rejection(
    detail: str,
) -> str:
    if detail.startswith(("different player", "candidate player")):
        return "PLAYER_MISMATCH"
    if detail.startswith("different year"):
        return "YEAR_MISMATCH"
    if detail.startswith("different serial"):
        return "SERIAL_DENOMINATOR_MISMATCH"
    if detail.startswith("autograph"):
        return "AUTOGRAPH_MISMATCH"
    if detail.startswith("memorabilia"):
        return "MEMORABILIA_MISMATCH"
    if detail.startswith("raw vs graded"):
        return "RAW_GRADED_MISMATCH"
    if detail.startswith("different grader"):
        return "GRADER_MISMATCH"
    if detail.startswith("different grade"):
        return "GRADE_MISMATCH"
    if detail.startswith(("different parallel", "candidate parallel")):
        return "PARALLEL_MISMATCH"
    if detail.startswith("rejecting risk"):
        return "REJECTING_RISK_FLAG"

    return "OTHER_MATCH_REJECT"


def _product_value(
    listing: Listing,
) -> str | None:
    if listing.identity is None:
        return None

    return listing.identity.set_name or listing.identity.brand


def _product_mismatch_reason(
    candidate: Listing,
    reference: Listing,
) -> str | None:
    left = _product_value(candidate)
    right = _product_value(reference)

    if not left or not right or _norm(left) == _norm(right):
        return None

    if (
        candidate.identity
        and reference.identity
        and candidate.identity.set_name
        and reference.identity.set_name
    ):
        return "SET_MISMATCH"

    return "BRAND_MISMATCH"


def _year_mismatch(
    candidate: Listing,
    reference: Listing,
) -> bool:
    if candidate.identity is None or reference.identity is None:
        return False

    left = normalize_card_year(candidate.identity.year)
    right = normalize_card_year(reference.identity.year)

    if left is None or right is None:
        return False

    return left != right


def diagnose_reference_rejections(
    candidate: Listing,
    references: list[Listing],
) -> list[ReferenceRejectionDiagnostic]:
    diagnostics: list[ReferenceRejectionDiagnostic] = []
    seen: set[tuple[str, str]] = set()

    for reference in references:
        key = (
            reference.source.casefold(),
            reference.external_id,
        )

        if key in seen:
            continue

        seen.add(key)
        reasons: list[str] = []
        details: list[str] = []
        match_level: str | None = None

        if _same_source_item(candidate, reference):
            _add(reasons, "SAME_ITEM")

        if _same_source(candidate, reference):
            _add(reasons, "SAME_STORE")

        if candidate.identity is None or reference.identity is None:
            _add(reasons, "MISSING_IDENTITY")

        if reference.currency.upper() != "AUD":
            _add(reasons, "NON_AUD")

        try:
            if _landed_aud(reference) is None:
                _add(reasons, "INVALID_PRICE")
        except (TypeError, ValueError):
            _add(reasons, "INVALID_PRICE")

        if reasons:
            diagnostics.append(
                ReferenceRejectionDiagnostic(
                    candidate_source=candidate.source,
                    candidate_external_id=candidate.external_id,
                    reference_source=reference.source,
                    reference_external_id=reference.external_id,
                    reasons=tuple(reasons),
                    match_level=match_level,
                    details=tuple(details),
                )
            )
            continue

        assert candidate.identity is not None
        assert reference.identity is not None

        risk_flags = title_risk_flags(reference.title)
        assessment = assess_match(
            candidate.identity,
            reference.identity,
            risk_flags=risk_flags,
        )
        match_level = assessment.match_level.value

        for detail in assessment.rejection_reasons:
            details.append(detail)
            _add(reasons, _map_match_rejection(detail))

        if _year_mismatch(candidate, reference):
            _add(reasons, "YEAR_MISMATCH")

        product_reason = _product_mismatch_reason(
            candidate,
            reference,
        )

        if product_reason:
            _add(reasons, product_reason)

        if not _same_known_card_number(candidate, reference):
            _add(reasons, "CARD_NUMBER_MISMATCH")

        if (
            candidate.identity is not None
            and reference.identity is not None
            and candidate.identity.rookie != reference.identity.rookie
        ):
            _add(reasons, "ROOKIE_MISMATCH")

        if (
            assessment.match_level == MatchLevel.RELATED
            and not reasons
        ):
            _add(reasons, "RELATED_ONLY")

        if assessment.match_level == MatchLevel.REJECT and not reasons:
            _add(reasons, "OTHER_MATCH_REJECT")

        if not reasons:
            continue

        diagnostics.append(
            ReferenceRejectionDiagnostic(
                candidate_source=candidate.source,
                candidate_external_id=candidate.external_id,
                reference_source=reference.source,
                reference_external_id=reference.external_id,
                reasons=tuple(reasons),
                match_level=match_level,
                details=tuple(details),
            )
        )

    return diagnostics


def summarize_reference_rejections(
    diagnostics: list[ReferenceRejectionDiagnostic],
) -> dict[str, int]:
    counts: Counter[str] = Counter()

    for diagnostic in diagnostics:
        counts.update(diagnostic.reasons)

    return dict(sorted(counts.items()))


def build_reference_funnel(
    candidate: Listing,
    references: list[Listing],
) -> dict[str, int]:
    """
    Reporting-only cumulative cross-store identity funnel.

    Each stage counts only references that survived every prior stage.
    It does not create market references or alter matching decisions.
    """
    stages = [
        "CROSS_STORE",
        "IDENTITY_PRESENT",
        "SAME_PLAYER",
        "SAME_YEAR",
        "SAME_PRODUCT",
        "SAME_CARD_NUMBER",
        "SAME_PARALLEL",
        "SAME_SERIAL",
        "SAME_ROOKIE",
        "SAME_AUTO_MEM",
        "SAME_GRADING",
        "EXACT_STRONG",
    ]
    counts = {stage: 0 for stage in stages}
    seen: set[tuple[str, str]] = set()

    for reference in references:
        key = (reference.source.casefold(), reference.external_id)

        if key in seen:
            continue
        seen.add(key)

        if _same_source(candidate, reference):
            continue

        counts["CROSS_STORE"] += 1

        if candidate.identity is None or reference.identity is None:
            continue
        counts["IDENTITY_PRESENT"] += 1

        left = candidate.identity
        right = reference.identity

        if not left.player or not right.player or _norm(left.player) != _norm(right.player):
            continue
        counts["SAME_PLAYER"] += 1

        left_year = normalize_card_year(left.year)
        right_year = normalize_card_year(right.year)
        if left_year is None or right_year is None or left_year != right_year:
            continue
        counts["SAME_YEAR"] += 1

        left_product = _product_value(candidate)
        right_product = _product_value(reference)
        if not left_product or not right_product or _norm(left_product) != _norm(right_product):
            continue
        counts["SAME_PRODUCT"] += 1

        if not left.card_number or not right.card_number or _norm(left.card_number) != _norm(right.card_number):
            continue
        counts["SAME_CARD_NUMBER"] += 1

        if not left.parallel or not right.parallel or _norm(left.parallel) != _norm(right.parallel):
            continue
        counts["SAME_PARALLEL"] += 1

        if left.serial_total is None or right.serial_total is None:
            continue
        if left.serial_total != right.serial_total:
            continue
        counts["SAME_SERIAL"] += 1

        if left.rookie != right.rookie:
            continue
        counts["SAME_ROOKIE"] += 1

        if left.autograph != right.autograph or left.memorabilia != right.memorabilia:
            continue
        counts["SAME_AUTO_MEM"] += 1

        left_graded = left.grader is not None or left.grade is not None
        right_graded = right.grader is not None or right.grade is not None
        if left_graded != right_graded:
            continue
        if left.grader and right.grader and _norm(left.grader) != _norm(right.grader):
            continue
        if left.grade is not None or right.grade is not None:
            if left.grade is None or right.grade is None:
                continue
            if float(left.grade) != float(right.grade):
                continue
        counts["SAME_GRADING"] += 1

        assessment = assess_match(
            left,
            right,
            risk_flags=title_risk_flags(reference.title),
        )
        if assessment.match_level in (MatchLevel.EXACT, MatchLevel.STRONG):
            counts["EXACT_STRONG"] += 1

    return counts
