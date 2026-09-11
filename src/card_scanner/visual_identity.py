from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps


CONSISTENT_MAX_DISTANCE = 12
POSSIBLE_MISMATCH_MIN_DISTANCE = 50


def difference_hash_bytes(content: bytes) -> int:
    """Return a 64-bit dHash for a listing image.

    This is deliberately used as rejection/audit evidence only. Image similarity
    must never create an exact-card match because slabs, crops, lighting and
    marketplace processing can make different photos of the same card vary.
    """
    with Image.open(BytesIO(content)) as opened:
        image = ImageOps.exif_transpose(opened).convert("L")
        image = image.resize((9, 8), Image.Resampling.LANCZOS)
        pixels = list(image.getdata())

    value = 0
    bit = 0
    for row in range(8):
        offset = row * 9
        for col in range(8):
            if pixels[offset + col] > pixels[offset + col + 1]:
                value |= 1 << bit
            bit += 1
    return value


def hamming_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def classify_visual_distance(distance: int) -> str:
    """Conservative interpretation of a 64-bit dHash distance."""
    if distance <= CONSISTENT_MAX_DISTANCE:
        return "VISUALLY_CONSISTENT"
    if distance >= POSSIBLE_MISMATCH_MIN_DISTANCE:
        return "POSSIBLE_VISUAL_MISMATCH"
    return "INCONCLUSIVE"
