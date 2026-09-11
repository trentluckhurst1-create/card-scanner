from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Any

import httpx

from card_scanner.visual_identity import (
    classify_visual_distance,
    difference_hash_bytes,
    hamming_distance,
)


MAX_IMAGE_BYTES = 8 * 1024 * 1024


def _card_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("source") or "").casefold(),
        str(row.get("external_id") or ""),
    )


def _fetch_hash(
    url: str | None,
    *,
    client: httpx.Client,
    cache: dict[str, int | None],
) -> int | None:
    if not url:
        return None
    if url in cache:
        return cache[url]
    try:
        response = client.get(url)
        response.raise_for_status()
        content = response.content
        if not content or len(content) > MAX_IMAGE_BYTES:
            cache[url] = None
            return None
        cache[url] = difference_hash_bytes(content)
    except Exception:
        cache[url] = None
    return cache[url]


def build_visual_audit(
    payload: dict[str, Any],
    *,
    client: httpx.Client,
) -> dict[str, Any]:
    cards = {
        _card_key(card): card
        for card in payload.get("market_cards") or []
    }
    image_cache: dict[str, int | None] = {}
    audited_groups: list[dict[str, Any]] = []
    mismatch_pairs: list[dict[str, Any]] = []

    for group in payload.get("comparison_groups") or []:
        representatives: dict[str, dict[str, Any]] = {}
        for listing in group.get("listings") or []:
            source = str(listing.get("source") or "").casefold()
            external_id = str(listing.get("external_id") or "")
            card = cards.get((source, external_id))
            if card and source not in representatives:
                representatives[source] = card

        pair_results: list[dict[str, Any]] = []
        for left, right in itertools.combinations(representatives.values(), 2):
            left_hash = _fetch_hash(
                left.get("image_url"), client=client, cache=image_cache
            )
            right_hash = _fetch_hash(
                right.get("image_url"), client=client, cache=image_cache
            )
            if left_hash is None or right_hash is None:
                status = "UNAVAILABLE"
                distance = None
            else:
                distance = hamming_distance(left_hash, right_hash)
                status = classify_visual_distance(distance)

            pair = {
                "left_source": left.get("source"),
                "left_external_id": left.get("external_id"),
                "left_image_url": left.get("image_url"),
                "right_source": right.get("source"),
                "right_external_id": right.get("external_id"),
                "right_image_url": right.get("image_url"),
                "distance": distance,
                "status": status,
            }
            pair_results.append(pair)
            if status == "POSSIBLE_VISUAL_MISMATCH":
                mismatch_pairs.append(
                    {
                        "comparison_key": group.get("comparison_key"),
                        "player": group.get("player"),
                        "year": group.get("year"),
                        **pair,
                    }
                )

        statuses = {pair["status"] for pair in pair_results}
        if "POSSIBLE_VISUAL_MISMATCH" in statuses:
            group_status = "POSSIBLE_VISUAL_MISMATCH"
        elif pair_results and statuses == {"VISUALLY_CONSISTENT"}:
            group_status = "VISUALLY_CONSISTENT"
        elif pair_results and statuses != {"UNAVAILABLE"}:
            group_status = "INCONCLUSIVE"
        else:
            group_status = "UNAVAILABLE"

        audited_groups.append(
            {
                "comparison_key": group.get("comparison_key"),
                "player": group.get("player"),
                "year": group.get("year"),
                "store_count": group.get("store_count"),
                "visual_status": group_status,
                "pairs": pair_results,
            }
        )

    status_counts: dict[str, int] = {}
    for row in audited_groups:
        status = str(row["visual_status"])
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "schema_version": 1,
        "purpose": "CONSERVATIVE_PHOTO_MISMATCH_AUDIT_ONLY",
        "governance": {
            "visual_similarity_can_create_exact_match": False,
            "visual_mismatch_can_trigger_manual_or_future_rejection_review": True,
            "text_and_structured_identity_remain_primary": True,
        },
        "groups_audited": len(audited_groups),
        "status_counts": status_counts,
        "possible_mismatch_pair_count": len(mismatch_pairs),
        "possible_mismatch_pairs": mismatch_pairs,
        "groups": audited_groups,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit exact comparison groups for obvious photo mismatches."
    )
    parser.add_argument("--feed", default="docs/comparison.json")
    parser.add_argument(
        "--output", default="artifacts/visual_exactness_audit.json"
    )
    args = parser.parse_args()

    payload = json.loads(Path(args.feed).read_text(encoding="utf-8"))
    with httpx.Client(
        timeout=15.0,
        follow_redirects=True,
        headers={"User-Agent": "card-scanner-visual-audit/1.0"},
    ) as client:
        audit = build_visual_audit(payload, client=client)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("CARD_SCANNER_VISUAL_EXACTNESS_AUDIT=PASS")
    print(f"GROUPS_AUDITED={audit['groups_audited']}")
    print(
        "POSSIBLE_VISUAL_MISMATCH_PAIRS="
        f"{audit['possible_mismatch_pair_count']}"
    )
    print(f"OUTPUT={output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
