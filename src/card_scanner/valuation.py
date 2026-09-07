from __future__ import annotations
from dataclasses import dataclass
from statistics import median
from typing import Iterable

@dataclass
class Comp:
    sold_price_aud: float
    age_days: float
    similarity: float  # 0..1

def robust_fair_value(comps: Iterable[Comp]) -> tuple[float | None, float, int]:
    comps = [c for c in comps if c.sold_price_aud > 0 and c.similarity > 0]
    if not comps:
        return None, 0.0, 0

    # Weighted by exactness and recency, with a mild recency decay.
    weighted = []
    for c in comps:
        recency = max(0.25, 1.0 / (1.0 + c.age_days / 90.0))
        weight = c.similarity * recency
        repeats = max(1, round(weight * 10))
        weighted.extend([c.sold_price_aud] * repeats)

    fair = median(weighted)
    avg_similarity = sum(c.similarity for c in comps) / len(comps)
    depth = min(len(comps) / 8.0, 1.0)
    confidence = min(1.0, 0.65 * avg_similarity + 0.35 * depth)
    return round(fair, 2), round(confidence, 3), len(comps)
