import cv2
import numpy as np
import pytest

from ALGORITHMS.core.inference import generate_positions


@pytest.mark.parametrize("length", [224, 1344, 1792])
def test_tiles_cover_entire_axis(length):
    positions = generate_positions(length)
    covered = np.zeros(length, dtype=bool)
    for position in positions:
        assert 0 <= position <= length - 224
        covered[position : position + 224] = True
    assert covered.all()
    assert positions[-1] == length - 224
    assert len(set(positions)) == len(positions)


def test_alignment_preserves_class_ids():
    mask = np.tile(np.arange(4, dtype=np.uint8), (768, 144))
    resized = cv2.resize(mask, (1792, 1344), interpolation=cv2.INTER_NEAREST)
    assert resized.shape == (1344, 1792)
    assert set(np.unique(resized)) == {0, 1, 2, 3}
