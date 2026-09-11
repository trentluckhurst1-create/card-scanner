from __future__ import annotations

import re
from typing import Any


def norm_token(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    text = str(value).casefold().strip()
    return re.sub(r"[^a-z0-9]+", "", text)


def normalize_card_number(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"^\s*(?:#|no\.?\s*)", "", text, flags=re.I).strip()
    compact = re.sub(r"[^A-Za-z0-9]+", "", text).casefold()
    if compact.isdigit():
        return str(int(compact))
    return compact


def normalize_grade(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return norm_token(value)
    if number.is_integer():
        return str(int(number))
    return (f"{number:.3f}").rstrip("0").rstrip(".")


def normalize_product(*, brand: Any, set_name: Any) -> tuple[str, str]:
    """Return (brand, set-core) tokens without weakening product identity.

    A set name may include its brand prefix on one store and omit it on another.
    Example: brand=Topps, set=Topps Chrome and brand=Topps, set=Chrome should
    canonicalize identically. We never infer a missing brand.
    """
    brand_token = norm_token(brand)
    set_token = norm_token(set_name)
    if set_token and brand_token and set_token.startswith(brand_token):
        remainder = set_token[len(brand_token):]
        if remainder:
            set_token = remainder
    if not set_token:
        set_token = brand_token
    return brand_token, set_token


def canonical_exact_components(*, sport: Any, identity: dict[str, Any]) -> dict[str, str]:
    brand, product = normalize_product(
        brand=identity.get("brand"),
        set_name=identity.get("set_name"),
    )
    return {
        "sport": norm_token(sport),
        "player": norm_token(identity.get("player")),
        "year": norm_token(identity.get("year")),
        "brand": brand,
        "product": product,
        "card_number": normalize_card_number(identity.get("card_number")),
        "parallel": norm_token(identity.get("parallel")),
        "serial_current": norm_token(identity.get("serial_current")),
        "serial_total": norm_token(identity.get("serial_total")),
        "grader": norm_token(identity.get("grader")),
        "grade": normalize_grade(identity.get("grade")),
        "autograph": norm_token(identity.get("autograph")),
        "memorabilia": norm_token(identity.get("memorabilia")),
        "rookie": norm_token(identity.get("rookie")),
    }


def exact_components_eligible(components: dict[str, str]) -> bool:
    core = (
        components.get("sport"),
        components.get("player"),
        components.get("year"),
        components.get("brand"),
        components.get("product"),
    )
    discriminator = any(
        components.get(field)
        for field in ("card_number", "parallel", "serial_total")
    )
    return all(core) and discriminator


def exact_signature(components: dict[str, str]) -> str:
    order = (
        "sport", "player", "year", "brand", "product", "card_number",
        "parallel", "serial_current", "serial_total", "grader", "grade",
        "autograph", "memorabilia", "rookie",
    )
    return "|".join(components.get(field, "") for field in order)


def exact_match_reasons(components: dict[str, str]) -> list[str]:
    reasons = ["same player", "same year", "same brand/product"]
    if components.get("card_number"):
        reasons.append("same card number")
    if components.get("parallel"):
        reasons.append("same parallel")
    if components.get("serial_current"):
        reasons.append("same serial copy number")
    if components.get("serial_total"):
        reasons.append("same serial denominator")
    if components.get("grader") or components.get("grade"):
        reasons.append("same grading state")
    if components.get("autograph") == "1":
        reasons.append("same autograph state")
    if components.get("memorabilia") == "1":
        reasons.append("same memorabilia state")
    if components.get("rookie") == "1":
        reasons.append("same rookie state")
    return reasons
