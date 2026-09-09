from __future__ import annotations

import re
from dataclasses import dataclass

from .models import CardIdentity


@dataclass(frozen=True)
class YearEvidence:
    source: str
    year: str
    player: str | None
    set_name: str | None
    card_number: str | None
    parallel: str | None
    reference: str | None = None


@dataclass(frozen=True)
class YearResolution:
    status: str
    year: str | None
    accepted_sources: tuple[str, ...]
    rejected_sources: tuple[str, ...]
    reason: str


def _norm(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _same(left: str | None, right: str | None) -> bool:
    return bool(_norm(left)) and _norm(left) == _norm(right)


def _product_match(left: str | None, right: str | None) -> bool:
    a = _norm(left)
    b = _norm(right)
    if not a or not b:
        return False
    return a == b


def evidence_matches_identity(
    identity: CardIdentity,
    evidence: YearEvidence,
) -> bool:
    if not identity.player or not _same(
        identity.player, evidence.player
    ):
        return False

    product = identity.set_name or identity.brand
    if not product or not _product_match(
        product, evidence.set_name
    ):
        return False

    if not identity.card_number or not _same(
        identity.card_number, evidence.card_number
    ):
        return False

    if identity.parallel:
        if not evidence.parallel:
            return False
        if not _same(identity.parallel, evidence.parallel):
            return False

    return bool(re.fullmatch(r"(?:19|20)\d{2}", evidence.year))


def resolve_year(
    identity: CardIdentity,
    evidence: list[YearEvidence],
    min_independent_sources: int = 2,
) -> YearResolution:
    if identity.year:
        return YearResolution(
            status="ALREADY_KNOWN",
            year=identity.year,
            accepted_sources=(),
            rejected_sources=(),
            reason="target identity already contains year",
        )

    accepted = [
        item
        for item in evidence
        if evidence_matches_identity(identity, item)
    ]

    rejected = [
        item.source
        for item in evidence
        if item not in accepted
    ]

    by_source: dict[str, YearEvidence] = {}
    for item in accepted:
        by_source.setdefault(item.source.lower(), item)

    accepted_unique = list(by_source.values())

    if len(accepted_unique) < min_independent_sources:
        return YearResolution(
            status="INSUFFICIENT_EVIDENCE",
            year=None,
            accepted_sources=tuple(
                item.source for item in accepted_unique
            ),
            rejected_sources=tuple(rejected),
            reason="insufficient independent exact-identity sources",
        )

    years = {item.year for item in accepted_unique}

    if len(years) != 1:
        return YearResolution(
            status="CONFLICT",
            year=None,
            accepted_sources=tuple(
                item.source for item in accepted_unique
            ),
            rejected_sources=tuple(rejected),
            reason="independent exact-identity sources disagree on year",
        )

    year = next(iter(years))

    return YearResolution(
        status="RESOLVED",
        year=year,
        accepted_sources=tuple(
            item.source for item in accepted_unique
        ),
        rejected_sources=tuple(rejected),
        reason="independent exact-identity sources agree on year",
    )
