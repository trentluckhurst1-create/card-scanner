from __future__ import annotations

import re

from .models import CardIdentity
from .year_normalization import normalize_card_year


def _clean(value: str | None) -> str | None:
    if not value:
        return None

    value = " ".join(str(value).split()).strip()

    return value or None


def identity_signature(identity: CardIdentity) -> str:
    """
    Strict machine-readable identity used to group likely exact cards.
    Card serial numerator is deliberately excluded: 38/50 and 7/50
    are the same parallel for valuation purposes.
    """

    fields = [
        identity.sport,
        normalize_card_year(identity.year) or identity.year,
        identity.set_name or identity.brand,
        identity.player,
        identity.card_number,
        identity.parallel,
        (
            f"/{identity.serial_total}"
            if identity.serial_total
            else None
        ),
        "RC" if identity.rookie else None,
        "AUTO" if identity.autograph else None,
        "MEM" if identity.memorabilia else None,
        identity.grader,
        (
            str(identity.grade)
            if identity.grade is not None
            else None
        ),
    ]

    cleaned = [
        _clean(x)
        for x in fields
        if _clean(x)
    ]

    return " | ".join(cleaned)


def exact_comp_query(identity: CardIdentity) -> str:
    """
    High-precision marketplace search.

    Serial numerator is omitted. Denominator is kept because /5, /50,
    /250 etc can represent materially different cards.
    """

    parts: list[str] = []

    if identity.year:
        parts.append(identity.year)

    if identity.set_name:
        parts.append(identity.set_name)
    elif identity.brand:
        parts.append(identity.brand)

    if identity.player:
        parts.append(identity.player)

    if identity.card_number:
        parts.append(f"#{identity.card_number}")

    if identity.parallel:
        parts.append(identity.parallel)

    if identity.serial_total:
        parts.append(f"/{identity.serial_total}")

    if identity.rookie:
        if (
            identity.set_name
            and "Bowman" in identity.set_name
        ):
            parts.append("1st")
        else:
            parts.append("rookie")

    if identity.autograph:
        parts.append("auto")

    if identity.memorabilia:
        parts.append("relic")

    if identity.grader:
        grade = (
            f" {identity.grade:g}"
            if identity.grade is not None
            else ""
        )

        parts.append(
            f"{identity.grader}{grade}"
        )

    return " ".join(
        part
        for part in parts
        if part
    )


def broad_comp_query(identity: CardIdentity) -> str:
    """
    Fallback search used when exact-card sales are too sparse.
    Removes grade, serial denominator and card number but retains
    set/player/parallel/rookie/auto structure.
    """

    parts: list[str] = []

    if identity.year:
        parts.append(identity.year)

    if identity.set_name:
        parts.append(identity.set_name)
    elif identity.brand:
        parts.append(identity.brand)

    if identity.player:
        parts.append(identity.player)

    if identity.parallel:
        parts.append(identity.parallel)

    if identity.rookie:
        parts.append("rookie")

    if identity.autograph:
        parts.append("auto")

    if identity.memorabilia:
        parts.append("relic")

    return " ".join(parts)


def comp_quality(identity: CardIdentity) -> float:
    """
    Measures whether we know enough about the card to permit
    serious comparable matching.

    This is not valuation confidence.
    """

    score = 0.0

    if identity.year:
        score += 0.10

    if identity.set_name or identity.brand:
        score += 0.15

    if identity.player:
        score += 0.30

    if identity.card_number:
        score += 0.10

    if identity.parallel:
        score += 0.15

    if identity.serial_total:
        score += 0.10

    if identity.rookie:
        score += 0.04

    if identity.autograph:
        score += 0.04

    if identity.grader:
        score += 0.01

    if identity.grade is not None:
        score += 0.01

    return round(
        min(score, 1.0),
        3,
    )
