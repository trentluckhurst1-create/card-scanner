from __future__ import annotations

import re
from dataclasses import dataclass

from .models import CardIdentity, MatchLevel
from .year_normalization import normalize_card_year


REJECTING_RISK_FLAGS = {
    "DIGITAL",
    "CUSTOM",
    "REPRINT",
    "LOT_OR_BUNDLE",
    "BOX_OR_PACK",
}


@dataclass(frozen=True)
class MatchAssessment:
    match_level: MatchLevel
    match_score: float
    match_reasons: list[str]
    rejection_reasons: list[str]


def _norm(value: object | None) -> str | None:
    if value is None:
        return None

    text = re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()

    return " ".join(text.split()) or None


def _same(a: object | None, b: object | None) -> bool:
    return _norm(a) == _norm(b)


def _same_year(
    a: str | None,
    b: str | None,
) -> bool:
    left = normalize_card_year(a)
    right = normalize_card_year(b)

    if left is None or right is None:
        return False

    return left == right


def _has_grading(identity: CardIdentity) -> bool:
    return bool(identity.grader or identity.grade is not None)


def _add_presence_score(
    source: CardIdentity,
    candidate: CardIdentity,
    attr: str,
    label: str,
    weight: float,
    reasons: list[str],
) -> float:
    left = getattr(source, attr)
    right = getattr(candidate, attr)

    if left is None or right is None:
        return 0.0

    if _same(left, right):
        reasons.append(label)
        return weight

    return 0.0


def _add_year_score(
    source: CardIdentity,
    candidate: CardIdentity,
    reasons: list[str],
) -> float:
    if source.year is None or candidate.year is None:
        return 0.0

    if _same_year(source.year, candidate.year):
        reasons.append("same year")
        return 0.12

    return 0.0


def assess_match(
    source: CardIdentity,
    candidate: CardIdentity,
    risk_flags: list[str] | None = None,
) -> MatchAssessment:
    reasons: list[str] = []
    rejections: list[str] = []
    risk_flags = risk_flags or []

    rejecting_flags = sorted(REJECTING_RISK_FLAGS.intersection(risk_flags))
    if rejecting_flags:
        rejections.append(
            "rejecting risk flags: " + ", ".join(rejecting_flags)
        )

    if source.player and candidate.player:
        if _same(source.player, candidate.player):
            reasons.append("same player")
        else:
            rejections.append(
                f"different player: {source.player} vs {candidate.player}"
            )
    elif source.player:
        rejections.append("candidate player missing")

    if source.year and candidate.year:
        if _same_year(source.year, candidate.year):
            reasons.append("same year")
        else:
            rejections.append(
                f"different year: {source.year} vs {candidate.year}"
            )

    if source.serial_total and candidate.serial_total:
        if source.serial_total == candidate.serial_total:
            reasons.append("same serial denominator")
        else:
            rejections.append(
                f"different serial denominator: /{source.serial_total} vs /{candidate.serial_total}"
            )

    if source.autograph != candidate.autograph:
        rejections.append("autograph status mismatch")

    if source.memorabilia != candidate.memorabilia:
        rejections.append("memorabilia status mismatch")

    if _has_grading(source) != _has_grading(candidate):
        rejections.append("raw vs graded mismatch")

    if source.grader and candidate.grader:
        if _same(source.grader, candidate.grader):
            reasons.append("same grader")
        else:
            rejections.append(
                f"different grader: {source.grader} vs {candidate.grader}"
            )

    if source.grade is not None and candidate.grade is not None:
        if float(source.grade) == float(candidate.grade):
            reasons.append("same grade")
        else:
            rejections.append(
                f"different grade: {source.grade:g} vs {candidate.grade:g}"
            )

    if source.parallel and candidate.parallel:
        if _same(source.parallel, candidate.parallel):
            reasons.append("same parallel")
        else:
            rejections.append(
                f"different parallel: {source.parallel} vs {candidate.parallel}"
            )
    elif source.parallel:
        rejections.append("candidate parallel missing")

    if any(
        reason.startswith(("different player", "candidate player", "different year", "different serial", "autograph", "memorabilia", "raw vs graded", "different grader", "different grade", "different parallel", "candidate parallel", "rejecting risk"))
        for reason in rejections
    ):
        return MatchAssessment(
            match_level=MatchLevel.REJECT,
            match_score=0.0,
            match_reasons=reasons,
            rejection_reasons=rejections,
        )

    score = 0.0
    score += _add_presence_score(source, candidate, "player", "same player", 0.25, reasons)
    score += _add_year_score(source, candidate, reasons)
    score += _add_presence_score(source, candidate, "set_name", "same set", 0.14, reasons)
    score += _add_presence_score(source, candidate, "brand", "same brand", 0.08, reasons)
    score += _add_presence_score(source, candidate, "card_number", "same card number", 0.12, reasons)
    score += _add_presence_score(source, candidate, "parallel", "same parallel", 0.12, reasons)

    if source.serial_total and candidate.serial_total == source.serial_total:
        score += 0.08

    if source.rookie == candidate.rookie:
        score += 0.03
        if source.rookie:
            reasons.append("same rookie/1st status")

    if source.autograph == candidate.autograph:
        score += 0.03
        if source.autograph:
            reasons.append("same autograph status")

    if source.memorabilia == candidate.memorabilia:
        score += 0.02
        if source.memorabilia:
            reasons.append("same memorabilia status")

    if _has_grading(source) or _has_grading(candidate):
        if source.grader and candidate.grader and _same(source.grader, candidate.grader):
            score += 0.02
        if source.grade is not None and candidate.grade is not None and float(source.grade) == float(candidate.grade):
            score += 0.02

    exact_requirements = [
        not source.player or _same(source.player, candidate.player),
        not source.year or _same_year(source.year, candidate.year),
        not (source.set_name or source.brand)
        or _same(source.set_name or source.brand, candidate.set_name or candidate.brand),
        not source.card_number or _same(source.card_number, candidate.card_number),
        not source.parallel or _same(source.parallel, candidate.parallel),
        not source.serial_total or source.serial_total == candidate.serial_total,
        source.rookie == candidate.rookie,
        source.autograph == candidate.autograph,
        source.memorabilia == candidate.memorabilia,
        _has_grading(source) == _has_grading(candidate),
        not source.grader or _same(source.grader, candidate.grader),
        source.grade is None
        or (
            candidate.grade is not None
            and float(source.grade) == float(candidate.grade)
        ),
    ]

    score = round(min(score, 1.0), 3)

    if all(exact_requirements) and score >= 0.75:
        return MatchAssessment(MatchLevel.EXACT, max(score, 0.95), reasons, [])

    if score >= 0.72:
        return MatchAssessment(MatchLevel.STRONG, score, reasons, [])

    return MatchAssessment(MatchLevel.RELATED, score, reasons, [])
