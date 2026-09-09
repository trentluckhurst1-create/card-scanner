from __future__ import annotations

import re
from dataclasses import dataclass

from .comp_key import comp_quality
from .models import Listing


_GRADER_TOKEN_RE = re.compile(r'\b(?:PSA|BGS|SGC|CGC)\b', re.I)

_NON_CARD_PRODUCT_RE = re.compile(
    r'\b(?:'
    r'(?:sealed\s+)?(?:hobby|blaster|mega|retail|bundle)?\s*box'
    r'|(?:sealed\s+)?(?:value|jumbo|hobby|retail|slab)?\s*pack'
    r'|sealed\s+bundle'
    r'|bundle\s+box'
    r')\b',
    re.I,
)


@dataclass(frozen=True)
class UnderdescriptionSignal:
    code: str
    severity: str
    reason: str


@dataclass(frozen=True)
class UnderdescriptionAssessment:
    status: str
    risk_score: float
    identity_quality: float
    signals: tuple[UnderdescriptionSignal, ...]
    evidence_flags: tuple[str, ...]

    @property
    def signal_codes(self) -> tuple[str, ...]:
        return tuple(signal.code for signal in self.signals)


def assess_underdescription(listing: Listing) -> UnderdescriptionAssessment:
    '''
    Assess whether a seller title is sufficiently specific and internally
    coherent for reliable card identification.

    This is reporting/risk intelligence only. It does not infer hidden card
    attributes, change fair value, loosen matching, or create BUY decisions.
    '''
    identity = listing.identity

    if _NON_CARD_PRODUCT_RE.search(listing.title):
        return UnderdescriptionAssessment(
            status='NOT_APPLICABLE',
            risk_score=0.0,
            identity_quality=(
                comp_quality(identity)
                if identity is not None
                else 0.0
            ),
            signals=(),
            evidence_flags=('NON_CARD_PRODUCT',),
        )

    if identity is None:
        return UnderdescriptionAssessment(
            status='POOR_IDENTITY',
            risk_score=100.0,
            identity_quality=0.0,
            signals=(
                UnderdescriptionSignal(
                    code='MISSING_IDENTITY',
                    severity='high',
                    reason='listing has no parsed card identity',
                ),
            ),
            evidence_flags=(),
        )

    quality = comp_quality(identity)
    signals: list[UnderdescriptionSignal] = []
    evidence: list[str] = []

    def add(code: str, severity: str, reason: str) -> None:
        if code not in {signal.code for signal in signals}:
            signals.append(
                UnderdescriptionSignal(
                    code=code,
                    severity=severity,
                    reason=reason,
                )
            )

    if not identity.player:
        add(
            'MISSING_PLAYER',
            'high',
            'seller title does not resolve a reliable player identity',
        )

    if not identity.year:
        add(
            'MISSING_YEAR',
            'medium',
            'seller title does not specify a card year or season',
        )

    if not (identity.set_name or identity.brand):
        add(
            'MISSING_PRODUCT',
            'medium',
            'seller title does not resolve a recognized product or set',
        )

    grader_token_present = bool(_GRADER_TOKEN_RE.search(listing.title))
    if (
        grader_token_present
        and (identity.grader is None or identity.grade is None)
    ):
        add(
            'GRADE_LABEL_INCOMPLETE',
            'medium',
            'grading company is mentioned but a complete numeric grade was not parsed',
        )

    weak_core_identity = (
        not identity.player
        or not identity.year
        or not (identity.set_name or identity.brand)
    )

    if weak_core_identity and quality < 0.50:
        add(
            'VERY_LOW_IDENTITY_SPECIFICITY',
            'high',
            f'core card identity is incomplete and completeness is only {quality:.2f}',
        )

    if identity.serial_total is not None:
        evidence.append('SERIAL_SPECIFIED')
        if weak_core_identity:
            add(
                'SERIAL_WITH_WEAK_IDENTITY',
                'medium',
                'serial scarcity is specified but core card identity is incomplete',
            )

    if identity.card_number:
        evidence.append('CARD_NUMBER_SPECIFIED')
        if weak_core_identity:
            add(
                'CARD_NUMBER_WITH_WEAK_IDENTITY',
                'low',
                'card number is specified but core card identity is incomplete',
            )

    if identity.parallel:
        evidence.append('PARALLEL_SPECIFIED')

    if identity.grader and identity.grade is not None:
        evidence.append('GRADING_SPECIFIED')

    if (
        identity.player
        and not identity.year
        and not (identity.set_name or identity.brand)
    ):
        add(
            'GENERIC_PLAYER_LISTING',
            'medium',
            'title identifies a player but not the card year or product',
        )

    weights = {
        'low': 10.0,
        'medium': 25.0,
        'high': 45.0,
    }
    risk_score = min(
        100.0,
        sum(weights.get(signal.severity, 20.0) for signal in signals),
    )

    if any(signal.severity == 'high' for signal in signals):
        status = 'POOR_IDENTITY'
    elif signals:
        status = 'REVIEW'
    else:
        status = 'CLEAR'

    return UnderdescriptionAssessment(
        status=status,
        risk_score=round(risk_score, 2),
        identity_quality=quality,
        signals=tuple(signals),
        evidence_flags=tuple(evidence),
    )
