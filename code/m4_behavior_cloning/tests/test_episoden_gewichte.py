"""train.py --episoden-gewichte: gewichtetes Ziehen der Frames (Drehbias, 2026-11-17)."""

import sys
from pathlib import Path

import _paths  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps"))

import numpy as np


def test_weighted_sampler_follows_weights_and_skips_zero():
    from train import WeightedFrameSampler

    # Episode A: Frames 0..9 (Gewicht 1), B: 10..19 (Gewicht 3), C: 20..29 (Gewicht 0)
    frames = list(range(30))
    weights = [1.0] * 10 + [3.0] * 10 + [0.0] * 10
    sampler = WeightedFrameSampler(frames, weights, seed=0)
    assert len(sampler) == 30
    drawn = np.array([i for _ in range(200) for i in sampler])
    assert not np.any(drawn >= 20), "Gewicht 0 darf nie gezogen werden"
    share_b = np.mean(drawn >= 10)
    assert abs(share_b - 0.75) < 0.03, share_b


def test_weighted_sampler_is_reproducible_per_epoch():
    from train import WeightedFrameSampler

    a = WeightedFrameSampler(list(range(50)), [1.0] * 50, seed=7)
    b = WeightedFrameSampler(list(range(50)), [1.0] * 50, seed=7)
    first_a, first_b = list(a), list(b)
    assert first_a == first_b
    assert list(a) != first_a  # naechste Epoche, andere Ziehung
