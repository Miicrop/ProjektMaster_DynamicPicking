"""Grafik "Tischabdeckung" und Varianten-Schalter der Oberflaeche (Anwender 2026-11-02)."""

import json
import os

import _paths  # noqa: F401

import numpy as np

from bc import config
from bc.gui import coverage_map as cm
from bc.gui import recording
from bc.table import Keepout

from test_auto_layout import _points, _record


def _square_region(keepouts=()):
    points = {"ID%d" % k: xy for k, xy in enumerate(
        ((0.2, -0.3), (0.6, -0.3), (0.6, 0.0), (0.2, 0.0)))}
    return cm.Region(points, list(keepouts), 90.0, (0.4, -0.15), "Test")


def test_record_argv_carries_variant_switches():
    base = recording.record_argv("x", sequence="s.json")
    assert "--feste-lage" not in base and "--varianten-versatz" not in base
    fixed = recording.record_argv("x", sequence="s.json", variants=False, variant_shift=0.02)
    assert "--feste-lage" in fixed and "--varianten-versatz" not in fixed
    tuned = recording.record_argv("x", sequence="s.json", variant_shift=0.02, variant_yaw=10,
                                  coverage_roots=["data_vm"])
    assert tuned[tuned.index("--varianten-versatz") + 1] == "0.02"
    assert tuned[tuned.index("--varianten-drehung") + 1] == "10"
    assert tuned[tuned.index("--abdeckung") + 1] == "data_vm"
    # ohne Zuruecklegen gibt es keine Varianten
    assert "--feste-lage" not in recording.record_argv("x", sequence="s.json", put_back=False,
                                                       variants=False)


def test_snapshot_counts_like_record_and_marks_candidates():
    spots = [cm.EpisodeSpot("a/ep_00000", (0.25, -0.25), 90.0),
             cm.EpisodeSpot("a/ep_00001", (0.26, -0.24), 100.0),
             cm.EpisodeSpot("a/ep_00002", (0.27, -0.25), 80.0, discarded=True)]
    snap = cm.build_snapshot(_square_region(), spots, margin=0.03, yaw_range_deg=45.0)
    counts = snap.coverage.cell_count
    assert sum(counts.values()) == 2                  # verworfen zaehlt nicht
    assert max(counts.values()) == 2
    assert snap.candidates and all(counts[c] == 0 for c in snap.candidates)
    # Kandidaten liegen weit weg von der belegten Ecke
    for cell in snap.candidates:
        x, y, w, h = snap.cell_rect(cell)
        assert np.hypot(x + w / 2 - 0.25, y + h / 2 + 0.25) > 0.15
    assert sum(snap.coverage.yaw_count) == 2
    assert "2 Fahrt(en) gezählt" in snap.summary()
    assert cm.build_snapshot(None, spots) is None
    tiny = cm.build_snapshot(_square_region(), spots, margin=0.5)
    assert tiny.coverage is None and tiny.error


def test_episodes_and_region_come_from_the_target_folder(tmp_path):
    points, _ = _points(size=0.12)
    error, log, _ = _record(tmp_path, ["--episodes", "2", "--lagen", "2"], points)
    assert error is None, log[-2000:]
    root = tmp_path / "data"
    spots, latest = cm.load_episodes(root)
    assert len(spots) == 4 and latest is not None
    assert [s.source for s in spots] == ["geteacht", "variante", "automatisch", "variante"]
    assert len({s.group for s in spots}) == 2
    region = cm.region_from_meta(latest[1], latest[0])
    assert len(region.points) == 4 and region.pick_xy is not None
    snap = cm.build_snapshot(region, spots)
    assert sum(snap.coverage.cell_count.values()) == 4
    # derselbe Ordner zweimal (Zielordner + alle Tage): jede Episode einmal
    again, _ = cm.load_episodes([root, tmp_path])
    assert len(again) == 4
    # andere Art Roboter (Anlage) zaehlt nicht mit Sim-Episoden
    real, _ = cm.load_episodes(root, in_simulation=False)
    assert real == []


def test_map_draws_offscreen(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return
    app = QApplication.instance() or QApplication([])
    zone = Keepout("IGNORE", (0.3, -0.1), half_size=0.03)
    spots = [cm.EpisodeSpot("a/ep_%05d" % k, (0.3 + 0.05 * k, -0.2), 30.0 * k, group="G",
                            recorded_at="2026-11-02T10:0%d:00" % k) for k in range(3)]
    widget = cm.CoverageMap()
    widget.resize(420, 320)
    widget.set_snapshot(cm.build_snapshot(_square_region([zone]), spots),
                        run_since="2026-11-02T10:01:00")
    for _ in range(4):
        image = widget.grab().toImage()
        widget.rotate()
    assert image.width() == 420 and app is not None
    # ohne Daten: Hinweistext statt Absturz
    widget.set_snapshot(None)
    widget.grab()


def test_region_from_meta_without_table_is_none():
    assert cm.region_from_meta({"metadata": {}}) is None
    meta = {"metadata": {"table_points": {
        "ID0": {"pose_quat": [0.2, -0.3, 0, 1, 0, 0, 0]},
        "ID1": {"pose_quat": [0.6, -0.3, 0, 1, 0, 0, 0]},
        "ID2": {"pose_quat": [0.6, 0.0, 0, 1, 0, 0, 0]}},
        "keepout": [{"name": "IGNORE", "center": [0.4, -0.1], "half_size": 0.05}],
        "table": {"a": 0.0, "b": 0.0, "c": 0.0, "model": "eben"}}}
    region = cm.region_from_meta(json.loads(json.dumps(meta)), "ep_00003")
    assert len(region.points) == 3 and region.keepouts[0].half_size == 0.05
    assert region.source == "Episode ep_00003"
    assert config.AUTO_VARIANT_SHIFT_M > 0
