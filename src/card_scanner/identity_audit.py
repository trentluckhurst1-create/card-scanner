from __future__ import annotations

from dataclasses import dataclass

from .comp_key import comp_quality
from .identity import parse_identity
from .models import CardIdentity, IdentityAuditRow, Listing


def identity_explanations(identity: CardIdentity) -> list[str]:
    explanations: list[str] = []

    checks = [
        ("sport", identity.sport and identity.sport != "UNKNOWN"),
        ("year", identity.year),
        ("set", identity.set_name or identity.brand),
        ("player", identity.player),
        ("card number", identity.card_number),
        ("parallel", identity.parallel),
        ("serial denominator", identity.serial_total),
        ("rookie/1st", identity.rookie),
        ("autograph", identity.autograph),
        ("memorabilia", identity.memorabilia),
        ("grader", identity.grader),
        ("grade", identity.grade is not None),
    ]

    for label, present in checks:
        explanations.append(
            f"{label}: {'present' if present else 'missing'}"
        )

    return explanations


@dataclass
class IdentityAuditSummary:
    total: int
    player_coverage: float
    year_coverage: float
    set_coverage: float
    parallel_coverage: float
    serial_coverage: float
    card_number_coverage: float
    grade_coverage: float
    comp_ready_rate: float
    lowest_confidence: list[IdentityAuditRow]


def audit_identities(
    listings: list[Listing],
    low_confidence_limit: int = 10,
) -> IdentityAuditSummary:
    rows: list[IdentityAuditRow] = []

    for listing in listings:
        identity = listing.identity or parse_identity(
            listing.title,
            listing.sport,
        )
        confidence = comp_quality(identity)
        rows.append(
            IdentityAuditRow(
                external_id=listing.external_id,
                sport=listing.sport,
                title=listing.title,
                identity=identity,
                confidence=confidence,
                explanations=identity_explanations(identity),
            )
        )

    total = len(rows)

    def coverage(predicate) -> float:
        if total == 0:
            return 0.0

        return round(
            sum(1 for row in rows if predicate(row.identity)) / total * 100.0,
            2,
        )

    return IdentityAuditSummary(
        total=total,
        player_coverage=coverage(lambda identity: identity and identity.player),
        year_coverage=coverage(lambda identity: identity and identity.year),
        set_coverage=coverage(lambda identity: identity and (identity.set_name or identity.brand)),
        parallel_coverage=coverage(lambda identity: identity and identity.parallel),
        serial_coverage=coverage(lambda identity: identity and identity.serial_total),
        card_number_coverage=coverage(lambda identity: identity and identity.card_number),
        grade_coverage=coverage(lambda identity: identity and identity.grader and identity.grade is not None),
        comp_ready_rate=coverage(lambda identity: identity and comp_quality(identity) >= 0.70),
        lowest_confidence=sorted(
            rows,
            key=lambda row: row.confidence,
        )[:low_confidence_limit],
    )
