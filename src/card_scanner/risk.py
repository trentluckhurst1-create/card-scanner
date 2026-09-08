from __future__ import annotations

import re

from .models import CardIdentity, RiskFlag


RISK_PATTERNS = {
    "DIGITAL": (r"\b(digital|e-?card|nft)\b", "high", "title indicates a digital card"),
    "CUSTOM": (r"\b(custom|art card)\b", "high", "title indicates a custom card"),
    "REPRINT": (r"\b(reprint|facsimile|reproduction|replica)\b", "high", "title indicates a reprint or replica"),
    "LOT_OR_BUNDLE": (r"\b(lot|bundle|mixed lot|team lot|player lot|multi[- ]?card|matching pair|full team base set|team set|complete set|base set|full set)\b", "high", "title indicates a lot, bundle, or multi-card set"),
    "BOX_OR_PACK": (r"\b(box|pack|case break|sealed|hobby box|blaster)\b", "high", "title indicates sealed product rather than one card"),
    "DAMAGED": (r"\b(damaged|damage|crease|creased|scratch|scratched|print line|poor condition)\b", "medium", "title indicates condition damage"),
    "ALTERED": (r"\b(altered|trimmed)\b", "high", "title indicates alteration or trimming"),
    "AUTHENTIC_ONLY": (r"\b(authentic only|authentic auto)\b", "medium", "title indicates authentication without numeric grade"),
    "EXPIRED_REDEMPTION": (r"\b(expired redemption)\b", "high", "title indicates expired redemption"),
    "REDEMPTION": (r"\b(redemption)\b", "medium", "title indicates redemption"),
    "MISSING_AUTOGRAPH": (r"\b(missing autograph|missing auto|no autograph|no auto)\b", "high", "title indicates missing autograph"),
    "REPLACEMENT": (r"\b(replacement)\b", "medium", "title indicates replacement"),
    "PROOF_SAMPLE_PROMO": (r"\b(proof|sample|promo)\b", "low", "title indicates proof, sample, or promo"),
    "UNLICENSED": (r"\b(unlicensed|not licensed)\b", "medium", "title indicates unlicensed issue"),
    "UNKNOWN_VARIATION": (r"\b(unknown variation|unrecognized variation)\b", "medium", "title indicates unknown variation"),
}


def title_risk_details(title: str) -> list[RiskFlag]:
    flags = []

    for code, (pattern, severity, reason) in RISK_PATTERNS.items():
        if re.search(pattern, title, flags=re.I):
            flags.append(
                RiskFlag(
                    code=code,
                    severity=severity,
                    reason=reason,
                )
            )

    return flags


def title_risk_flags(title: str) -> list[str]:
    return sorted({flag.code for flag in title_risk_details(title)})


def structural_risk_details(
    target: CardIdentity,
    candidate: CardIdentity,
) -> list[RiskFlag]:
    flags: list[RiskFlag] = []

    def add(code: str, severity: str, reason: str):
        flags.append(RiskFlag(code=code, severity=severity, reason=reason))

    if target.serial_total and candidate.serial_total and target.serial_total != candidate.serial_total:
        add("WRONG_SERIAL_DENOMINATOR", "high", f"target /{target.serial_total} but candidate /{candidate.serial_total}")

    if target.autograph and not candidate.autograph:
        add("AUTO_EXPECTED_ABSENT", "high", "target is autograph but candidate is not")

    if (target.grader or target.grade is not None) and not (candidate.grader or candidate.grade is not None):
        add("GRADED_TARGET_RAW_CANDIDATE", "high", "target is graded but candidate is raw")

    if (target.set_name or target.brand) and (candidate.set_name or candidate.brand):
        if (target.set_name or target.brand).lower() != (candidate.set_name or candidate.brand).lower():
            add("DIFFERENT_SET", "medium", "candidate set differs from target")

    if target.year and candidate.year and target.year != candidate.year:
        add("DIFFERENT_YEAR", "high", "candidate year differs from target")

    if target.card_number and candidate.card_number and target.card_number.lower() != candidate.card_number.lower():
        add("DIFFERENT_CARD_NUMBER", "medium", "candidate card number differs from target")

    return flags


def risk_score(flags: list[RiskFlag]) -> float:
    weights = {
        "low": 10.0,
        "medium": 30.0,
        "high": 60.0,
    }

    score = sum(weights.get(flag.severity, 20.0) for flag in flags)

    return min(score, 100.0)
