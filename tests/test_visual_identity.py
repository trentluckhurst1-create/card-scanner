from io import BytesIO

from PIL import Image

from card_scanner.visual_identity import (
    classify_visual_distance,
    difference_hash_bytes,
    hamming_distance,
)


def _png(values):
    image = Image.new("L", (9, 8))
    image.putdata(values)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_identical_images_are_visually_consistent():
    values = list(range(72))
    left = difference_hash_bytes(_png(values))
    right = difference_hash_bytes(_png(values))
    distance = hamming_distance(left, right)
    assert distance == 0
    assert classify_visual_distance(distance) == "VISUALLY_CONSISTENT"


def test_opposite_horizontal_gradients_are_possible_mismatch():
    increasing = []
    decreasing = []
    for _ in range(8):
        increasing.extend(range(9))
        decreasing.extend(reversed(range(9)))
    left = difference_hash_bytes(_png(increasing))
    right = difference_hash_bytes(_png(decreasing))
    distance = hamming_distance(left, right)
    assert distance == 64
    assert classify_visual_distance(distance) == "POSSIBLE_VISUAL_MISMATCH"


def test_midrange_distance_is_inconclusive():
    assert classify_visual_distance(30) == "INCONCLUSIVE"
