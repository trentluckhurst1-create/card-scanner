from __future__ import annotations

import re


RISK_PATTERNS = {
    "DIGITAL": r"\b(digital|e-?card|nft)\b",
    "CUSTOM": r"\b(custom|art card)\b",
    "REPRINT": r"\b(reprint|facsimile|reproduction|replica)\b",
    "LOT_OR_BUNDLE": r"\b(lot|bundle|mixed lot|team lot|multi[- ]?card)\b",
    "BOX_OR_PACK": r"\b(box|pack|case break|sealed|hobby box|blaster)\b",
    "DAMAGED": r"\b(damaged|damage|crease|creased|scratch|scratched|print line|poor condition)\b",
    "ALTERED": r"\b(altered|trimmed)\b",
    "AUTHENTIC_ONLY": r"\b(authentic only|authentic auto)\b",
    "EXPIRED_REDEMPTION": r"\b(expired redemption)\b",
    "REDEMPTION": r"\b(redemption)\b",
    "MISSING_AUTOGRAPH": r"\b(missing autograph|missing auto|no autograph|no auto)\b",
    "UNKNOWN_VARIATION": r"\b(unknown variation|unrecognized variation)\b",
}


def title_risk_flags(title: str) -> list[str]:
    lower = title.lower()
    flags = [
        flag
        for flag, pattern in RISK_PATTERNS.items()
        if re.search(pattern, lower, flags=re.I)
    ]

    return sorted(set(flags))
