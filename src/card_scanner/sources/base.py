from __future__ import annotations
from abc import ABC, abstractmethod
from card_scanner.models import Listing

class ListingSource(ABC):
    name: str

    @abstractmethod
    def search(self, sport: str, query: str, limit: int = 50) -> list[Listing]:
        raise NotImplementedError
