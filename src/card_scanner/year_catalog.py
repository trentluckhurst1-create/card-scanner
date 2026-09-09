from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .models import CardIdentity
from .year_resolution import YearEvidence, YearResolution, resolve_year


class YearCatalogProvider(ABC):
    name: str
    persistence_allowed = False

    @abstractmethod
    def lookup_year_evidence(
        self,
        sport: str,
        identity: CardIdentity,
    ) -> list[YearEvidence]:
        raise NotImplementedError


@dataclass(frozen=True)
class YearCatalogAssessment:
    resolution: YearResolution
    providers_considered: tuple[str, ...]
    providers_succeeded: tuple[str, ...]
    provider_errors: tuple[str, ...]
    evidence_count: int


class MultiYearCatalogResolver:
    def __init__(
        self,
        providers: list[YearCatalogProvider],
        min_independent_sources: int = 2,
    ):
        self.providers = list(providers)
        self.min_independent_sources = max(
            2, int(min_independent_sources)
        )

    def resolve(
        self,
        sport: str,
        identity: CardIdentity,
    ) -> YearCatalogAssessment:
        considered: list[str] = []
        succeeded: list[str] = []
        errors: list[str] = []
        evidence: list[YearEvidence] = []

        for provider in self.providers:
            name = provider.name
            considered.append(name)

            try:
                rows = provider.lookup_year_evidence(
                    sport, identity
                )
            except Exception as exc:
                errors.append(
                    f"{name}: {type(exc).__name__}"
                )
                continue

            succeeded.append(name)

            for row in rows:
                if row.source.lower() != name.lower():
                    continue
                evidence.append(row)

        resolution = resolve_year(
            identity,
            evidence,
            min_independent_sources=self.min_independent_sources,
        )

        return YearCatalogAssessment(
            resolution=resolution,
            providers_considered=tuple(considered),
            providers_succeeded=tuple(succeeded),
            provider_errors=tuple(errors),
            evidence_count=len(evidence),
        )
