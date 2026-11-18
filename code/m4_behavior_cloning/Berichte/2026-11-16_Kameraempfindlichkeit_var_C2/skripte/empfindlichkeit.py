"""Wie stark reagiert var_C2 auf Kameraverschiebungen? (Anwender 2026-11-16)

Offline, ohne Roboter: je ausgewaehltem Takt einer Aufnahme geht die
Beobachtung (2 Takte Historie, beide Kameras, Zustand) in die Policy -- einmal
unveraendert, dann mit gestoertem Bild. Verglichen wird der vorhergesagte
Chunk (TCP per URDF-Vorwaertskinematik) gegen die ungestoerte Vorhersage mit
DEMSELBEN Diffusionsrauschen. Als Untergrenze dient dieselbe Beobachtung mit
anderem Rauschen (Streuung der Policy selbst).

Stoerungen (immer auf beide Historienbilder, wie eine verschobene Kamera):
  scene_dx10 / scene_dy10   Szenenbild 10 px verschoben (Spanne der Trainingstage 8-10 px)
  scene_rot5                Szenenbild 5 Grad um die Bildmitte gedreht (3-6 Grad)
  scene_aus / wrist_aus     Bild durch seine mittlere Farbe ersetzt (Kamera ausgeblendet)

    python empfindlichkeit.py <ausgabe-ordner> [--je-quelle 12] [--jeder 2]
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(r"E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning")
sys.path.insert(0, str(ROOT / "apps"))
import _bootstrap  # noqa: F401,E402

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402

from bc import config, replay  # noqa: E402
from bc.adapters.sim_robot import SimRobot  # noqa: E402
from bc.diffusion import DiffusionPolicyRunner  # noqa: E402

CHECKPOINT = ROOT / "checkpoints" / "C2_nur_griff_ohne_1111" / "policy"
EXPORT = ROOT / "datasets" / "var_C2" / "meta" / "bc_export.json"
NEUER_TAG = ROOT / "data" / "2026-11-11"     # nicht im Training von var_C2
#: Chunk-Index, an dem verglichen wird: Ende der ausgefuehrten Aktionen
#: (n_action_steps 8, neu geplant wird alle 2 -- 2 und 7 als Spanne)
IDX = (1, 7)
SEED, SEED2 = 1234, 98765


def shift(img, dx, dy):
    m = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(img, m, (img.shape[1], img.shape[0]), borderMode=cv2.BORDER_REFLECT)


def rotate(img, deg):
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), deg, 1.0)
    return cv2.warpAffine(img, m, (w, h), borderMode=cv2.BORDER_REFLECT)


def blank(img):
    return np.broadcast_to(img.reshape(-1, 3).mean(0).astype(img.dtype), img.shape).copy()


VARIANTEN = {
    "scene_dx10": ("scene", lambda im: shift(im, 10, 0)),
    "scene_dy10": ("scene", lambda im: shift(im, 0, 10)),
    "scene_rot5": ("scene", lambda im: rotate(im, 5.0)),
    "scene_aus": ("scene", blank),
    "wrist_aus": ("wrist", blank),
}


def episoden(je_quelle):
    """(Wurzel, Index, Herkunft) -- Validierung der Trainingstage + neuer Tag."""
    export = json.loads(EXPORT.read_text(encoding="utf-8"))
    info = json.loads((CHECKPOINT / "bc_policy.json").read_text(encoding="utf-8"))
    train = set(info["dataset"]["train_episodes"])
    val = [e for e in export["episodes"] if e["episode_index"] not in train]
    out, rng = [], np.random.default_rng(0)
    pick = rng.choice(len(val), size=min(je_quelle, len(val)), replace=False)
    for k in sorted(pick):
        e = val[k]
        root = ROOT / e["source"]
        idx = json.loads((root / "index.json").read_text(encoding="utf-8"))
        dirs = [x["dir"] for x in idx["episodes"]]
        out.append((root, dirs.index(e["source_dir"]), "val " + e["source"][-10:]))
    usable = replay.usable_episodes(NEUER_TAG)
    for i in rng.choice(usable, size=min(je_quelle, len(usable)), replace=False):
        out.append((NEUER_TAG, int(i), "neu 2026-11-11"))
    return out


def obs(arrays, t, cams, mod=None):
    o = {"observation.state": np.asarray(arrays["observation.state"][t], dtype=np.float32)}
    for c in cams:
        im = arrays["observation.images.%s" % c][t]
        if mod is not None and mod[0] == c:
            im = mod[1](im)
        o["observation.images.%s" % c] = im
    return o


def predict(runner, arrays, t, cams, mod=None, seed=SEED):
    runner.reset()
    for tt in (max(t - 1, 0), t):
        runner.observe(obs(arrays, tt, cams, mod))
    torch.manual_seed(seed)
    return runner.predict(None)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("out")
    p.add_argument("--je-quelle", type=int, default=12)
    p.add_argument("--jeder", type=int, default=2, help="jeder n-te Takt bis zum Griff")
    a = p.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    runner = DiffusionPolicyRunner(CHECKPOINT, device="auto")
    cams = runner.cameras
    robot = SimRobot()

    def tcp(chunk):
        return np.array([np.asarray(robot.fk(q[:6]), dtype=float)[:3] for q in chunk])

    rows = []
    t0 = time.perf_counter()
    eps = episoden(a.je_quelle)
    for n, (root, index, herkunft) in enumerate(eps):
        arrays = replay.load_arrays(root, index)
        act = np.asarray(arrays["action"], dtype=float)
        closing = np.flatnonzero((act[1:, 6] > config.GRIPPER_THRESHOLD)
                                 & (act[:-1, 6] <= config.GRIPPER_THRESHOLD))
        if not closing.size:
            continue
        grasp = int(closing[0]) + 1
        z = np.asarray(arrays["observation.state"], dtype=float)[:, 8]
        for t in range(1, grasp + 1, a.jeder):
            base = predict(runner, arrays, t, cams)
            tb = tcp(base[list(IDX)])
            row = {"herkunft": herkunft, "root": root.name, "episode": index, "takt": t,
                   "griff_takt": grasp, "hoehe_mm": 1e3 * (z[t] - z[grasp])}
            # Streuung der Policy selbst
            tn = tcp(predict(runner, arrays, t, cams, seed=SEED2)[list(IDX)])
            row["rauschen"] = (1e3 * np.linalg.norm(tn[:, :2] - tb[:, :2], axis=1)).tolist()
            # Abstand zur Aufnahme (Label) als Bezug
            lab = act[[min(t + i, len(act) - 1) for i in IDX]]
            tl = tcp(lab)
            row["label"] = (1e3 * np.linalg.norm(tl[:, :2] - tb[:, :2], axis=1)).tolist()
            for name, mod in VARIANTEN.items():
                tv = tcp(predict(runner, arrays, t, cams, mod)[list(IDX)])
                d = 1e3 * (tv - tb)
                row[name] = np.linalg.norm(d[:, :2], axis=1).tolist()
                row[name + "_dz"] = d[:, 2].tolist()
            rows.append(row)
        print("%2d/%d %s ep %d: %d Takte bis Griff, %.0f s" % (n + 1, len(eps), herkunft, index,
                                                              grasp, time.perf_counter() - t0),
              flush=True)
        (out / "takte.json").write_text(json.dumps(rows), encoding="utf-8")
    print("fertig: %d Takte -> %s" % (len(rows), out / "takte.json"))


if __name__ == "__main__":
    main()
