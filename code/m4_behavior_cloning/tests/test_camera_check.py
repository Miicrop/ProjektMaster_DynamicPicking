"""Kamerapruefung gegen die Aufnahme des Modells (bc/camera_check.py)."""

import contextlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import _paths  # noqa: F401

import cv2
import numpy as np

from bc import camera_check

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps"))
sys.path.insert(0, str(ROOT / "tools"))


def _scene(seed=0):
    """Texturiertes Testbild 240x320 (RGB) mit genug Merkmalen fuer ORB."""
    rng = np.random.default_rng(seed)
    img = np.full((240, 320, 3), 90, np.uint8)
    for _ in range(60):
        x, y = rng.integers(10, 300), rng.integers(10, 220)
        color = tuple(int(c) for c in rng.integers(30, 220, 3))
        cv2.rectangle(img, (int(x), int(y)), (int(x + rng.integers(5, 25)), int(y + rng.integers(5, 25))),
                      color, -1)
    return img


def _shift(img, dx=0.0, dy=0.0, rot=0.0):
    m = cv2.getRotationMatrix2D((160, 120), rot, 1.0)
    m[:, 2] += (dx, dy)
    return cv2.warpAffine(img, m, (320, 240), borderMode=cv2.BORDER_REFLECT)


def _reference():
    base = _scene()
    frames = [np.clip(base.astype(int) + d, 0, 255).astype(np.uint8) for d in (-6, -3, 0, 3, 6)]
    return camera_check.build_reference({"scene": frames}), base


def test_same_camera_is_ok():
    reference, base = _reference()
    assert reference["scene"]["episodes"] == 5
    result = camera_check.compare(reference, {"scene": base})[0]
    assert result["level"] == camera_check.OK, result["checks"]
    assert result["shift"]["shift_px"] < 1.0
    lines = camera_check.format_lines([result])
    assert lines[0].startswith("KAMERAPRUEFUNG scene: OK")


def test_brighter_light_warns():
    reference, base = _reference()
    bright = np.clip(base.astype(int) + 60, 0, 255).astype(np.uint8)
    result = camera_check.compare(reference, {"scene": bright})[0]
    assert result["level"] == camera_check.WARN
    assert any(lvl == camera_check.WARN and text.startswith("Helligkeit")
               for lvl, text in result["checks"])


def test_moved_or_turned_camera_warns():
    reference, base = _reference()
    for moved in (_shift(base, dx=8.0), _shift(base, rot=3.0)):
        result = camera_check.compare(reference, {"scene": moved})[0]
        assert result["level"] == camera_check.WARN
        assert any(lvl == camera_check.WARN and "Kameralage" in text for lvl, text in result["checks"])
    # kleiner Versatz bleibt in Ordnung
    result = camera_check.compare(reference, {"scene": _shift(base, dx=1.5)})[0]
    assert result["level"] == camera_check.OK, result["checks"]


def test_missing_image_warns():
    reference, _ = _reference()
    assert camera_check.compare(reference, {})[0]["level"] == camera_check.WARN


def test_tool_adds_reference_to_an_old_checkpoint(tmp_path):
    import kamera_referenz

    data = tmp_path / "data"
    for k in range(3):
        ep = data / ("ep_%05d" % k)
        ep.mkdir(parents=True)
        (ep / "meta.json").write_text(json.dumps({"discarded": k == 2}), encoding="utf-8")
        frames = np.stack([_scene()] * 2)
        np.savez_compressed(ep / "arrays.npz", observation__images__scene=frames)
    ckpt = tmp_path / "policy"
    ckpt.mkdir()
    (ckpt / "bc_policy.json").write_text(json.dumps(
        {"cameras": ["scene"], "dataset": {"sources": [str(data)]}}), encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()):
        assert kamera_referenz.main(["--checkpoint", str(ckpt)]) == 0
    info = json.loads((ckpt / "bc_policy.json").read_text(encoding="utf-8"))
    assert info["camera_reference"]["scene"]["episodes"] == 2      # verworfene nicht
    assert list(ckpt.glob("bc_policy.json.bak_*"))


class _Cap:
    def __init__(self, name, image):
        self.name, self._image = name, image

    def latest(self):
        return SimpleNamespace(image=self._image)


def test_infer_stops_before_driving_when_cameras_differ(tmp_path, monkeypatch):
    import infer

    from bc import config

    monkeypatch.setattr(config, "CAMERA_CHECK_SETTLE_S", 0.0)
    reference, base = _reference()
    info = {"camera_reference": reference}
    args = SimpleNamespace(replay=None, no_start_move=True, kamerapruefung="an")
    robot = SimpleNamespace(gripper_command=lambda closed: None)
    answers = []
    monkeypatch.setattr(infer, "ask", lambda prompt, default="": answers.append(prompt) or "n")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        ok = infer.camera_check_before_run(robot, [_Cap("scene", base)], info, None, None,
                                           args, False, tmp_path)
        bad = infer.camera_check_before_run(robot, [_Cap("scene", _shift(base, dx=10))], info,
                                            None, None, args, False, tmp_path)
        args.kamerapruefung = "warnen"
        warned = infer.camera_check_before_run(robot, [_Cap("scene", _shift(base, dx=10))], info,
                                               None, None, args, False, tmp_path)
    assert ok and not bad and warned
    assert len(answers) == 1                     # nur bei Abweichung und "an" gefragt
    assert "KAMERAPRUEFUNG gesamt: WARNUNG" in out.getvalue()
    assert (tmp_path / "kamerapruefung_scene.png").is_file()
    # ohne Referenz: nur Hinweis, gefahren wird
    with contextlib.redirect_stdout(io.StringIO()):
        assert infer.camera_check_before_run(robot, [], {}, None, None, args, False, tmp_path)
