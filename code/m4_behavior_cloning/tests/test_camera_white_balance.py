"""Weissabgleich der Aufnahme fuer die Inferenz (Befund 2026-11-24, G2c).

G2c wurde aus zwei Aufnahmetagen mit verschiedenem Blau trainiert; die
Inferenz setzte darum gar keinen festen Weissabgleich, die Kamera glich per
"Once" neutral ab, und die Policy sah ein Bild ohne den Rotstich des Trainings.
"""

import _paths  # noqa: F401

from bc import camera_settings as cs

A, B = [2.641, 1.0, 2.609], [2.641, 1.0, 1.898]


def test_single_value_is_used():
    rec = {"wrist": {"white_balance_ratios": [A], "white_balance_auto": ["Off"]}}
    assert cs.recorded_white_balance(rec, "wrist") == tuple(A)
    assert cs.recorded_white_balance_note(rec, "wrist") is None


def test_several_fixed_values_take_the_most_frequent():
    rec = {"wrist": {"white_balance_ratios": [B, A], "white_balance_episodes": [180, 399],
                     "white_balance_auto": ["Off"]}}
    assert cs.recorded_white_balance(rec, "wrist") == tuple(A)
    assert "399" in cs.recorded_white_balance_note(rec, "wrist")


def test_old_export_without_counts_takes_the_first():
    # so steht es in checkpoints/G2c_579_nur_griff (Export vor 2026-11-24)
    rec = {"wrist": {"white_balance_ratios": [A, B], "white_balance_auto": ["Off"]}}
    assert cs.recorded_white_balance(rec, "wrist") == tuple(A)


def test_once_recordings_stay_once():
    rec = {"wrist": {"white_balance_ratios": [A, B], "white_balance_auto": ["Once"]}}
    assert cs.recorded_white_balance(rec, "wrist") is None
    assert cs.recorded_white_balance({}, "wrist") is None


def test_collect_counts_episodes_per_white_balance():
    eps = [{"wrist": {"white_balance_ratios": A, "white_balance_auto": "Off"}}] * 3 \
        + [{"wrist": {"white_balance_ratios": B, "white_balance_auto": "Off"}}]
    out = cs.collect(eps)["wrist"]
    assert out["white_balance_ratios"] == [A, B]
    assert out["white_balance_episodes"] == [3, 1]
    assert cs.recorded_white_balance({"wrist": out}, "wrist") == tuple(A)
