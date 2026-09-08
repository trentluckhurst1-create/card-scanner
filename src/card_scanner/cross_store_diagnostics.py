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
