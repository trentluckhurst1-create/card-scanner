from __future__ import annotations

from abc import ABC, abstractmethod


class CurrencyProvider(ABC):
    @abstractmethod
    def to_aud(
        self,
        amount: float,
        currency: str,
    ) -> tuple[float | None, str]:
        raise NotImplementedError


class FxProvider(CurrencyProvider):
    pass


class AudOnlyCurrencyProvider(CurrencyProvider):
    def to_aud(
        self,
        amount: float,
        currency: str,
    ) -> tuple[float | None, str]:
        if currency.upper() == "AUD":
            return round(float(amount), 2), "CONVERTED"

        return None, "FX_PENDING"
