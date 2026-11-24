"""Woher kommen die Schwingbahnen? Je Fahrt Querabweichung der Policy gegen das Rauschen der Aufnahme.

Mit --replay laeuft je Regeltakt genau ein Bild weiter. Takt t der Fahrt sieht
also das Bild von Takt t der Aufnahme. Hat die Aufnahme dort die Rauschabweichung
r(t) = Ist-TCP - ideale TCP, und folgt die Policy den Bildern, dann zeigt ihre
Abweichung p(t) = TCP_Fahrt - ideale TCP in dieselbe Richtung.

Kennzahlen (nur quer zur idealen Bahn, Anflug bis zum Greifen der Aufnahme):
  amp_fahrt_mm / amp_aufn_mm : p95 der Querabweichung
  gleichlauf                  : sum(p.r) / sqrt(sum|p|^2 sum|r|^2), -1..1
  uebernahme                  : sum(p.r) / sum|r|^2 (wie viel vom Rauschen nachgefahren wird)
  welligkeit_mm               : p95 der Querabweichung nach Abzug eines gleitenden Mittels (1 s)
Aufruf: schwingen.py <rollout-ordner> [weitere ...] -> schwingen.json je Ordner
"""
import sys, os, json
from pathlib import Path
import numpy as np

ROOT = Path(r"E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "tools"))
import _bootstrap  # noqa
from bc import replay, config


def quer(dev, ideal):
    t = np.gradient(ideal, axis=0)
    n = np.linalg.norm(t, axis=1, keepdims=True)
    t = np.where(n > 1e-6, t / np.maximum(n, 1e-9), 0.0)
    return dev - (dev * t).sum(1, keepdims=True) * t


def smooth(x, w=15):
    k = np.ones(w) / w
    return np.stack([np.convolve(np.pad(x[:, i], (w // 2, w // 2), mode="edge"), k, mode="valid")
                     for i in range(x.shape[1])], 1)


for run in map(Path, sys.argv[1:]):
    files = sorted(run.glob("rollout_*.npz"))
    summ_path = run / "summary.json"
    eps = json.loads(summ_path.read_text(encoding="utf-8"))["episodes"] if summ_path.exists() else None
    rows = []
    for f in files:
        i = int(f.stem.split("_")[1])
        if eps is not None:
            rp = eps[i].get("replay") or {}
            data, idx = rp["root"], rp["episode"]
        else:
            continue
        arr = replay.load_arrays(data, idx)
        meta = json.loads((replay.episode_dir(data, idx) / "meta.json").read_text(encoding="utf-8"))["metadata"]
        st = np.asarray(arr["observation.state"], float)
        ideal = np.asarray(arr["aux.pose_ideal"], float)[:, :3]
        act = np.asarray(arr["action"], float)
        close = np.flatnonzero(act[:, 6] > config.GRIPPER_THRESHOLD)
        n_app = int(close[0]) if len(close) else len(ideal)
        tcp = np.asarray(np.load(f)["tcp"], float)[:, :3]
        n = min(n_app, len(tcp))
        r = quer(st[:n, 6:9] - ideal[:n], ideal[:n])
        p = quer(tcp[:n] - ideal[:n], ideal[:n])
        dot = float((p * r).sum())
        rows.append(dict(
            lauf=i, data=data, episode=idx, block=meta.get("block"), noise=round(float(meta.get("noise_scale") or 0), 2),
            light=meta.get("light"), camera=meta.get("camera_pose"),
            amp_fahrt_mm=round(1e3 * float(np.percentile(np.linalg.norm(p, axis=1), 95)), 1),
            amp_aufn_mm=round(1e3 * float(np.percentile(np.linalg.norm(r, axis=1), 95)), 1),
            gleichlauf=round(dot / max(1e-12, np.sqrt((p * p).sum() * (r * r).sum())), 2),
            uebernahme=round(dot / max(1e-12, float((r * r).sum())), 2),
            welligkeit_mm=round(1e3 * float(np.percentile(np.linalg.norm(p - smooth(p), axis=1), 95)), 1),
            welligkeit_aufn_mm=round(1e3 * float(np.percentile(np.linalg.norm(r - smooth(r), axis=1), 95)), 1)))
    (run / "schwingen.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    if not rows:
        print(run, "keine Fahrten"); continue
    A = {k: np.array([x[k] for x in rows], float) for k in rows[0] if isinstance(rows[0][k], (int, float))}
    print("\n%s: %d Fahrten" % (run.name, len(rows)))
    print("  Querabweichung p95 Fahrt median %.1f mm, Aufnahme median %.1f mm" % (np.median(A["amp_fahrt_mm"]), np.median(A["amp_aufn_mm"])))
    print("  Gleichlauf median %.2f, Uebernahme median %.2f" % (np.median(A["gleichlauf"]), np.median(A["uebernahme"])))
    print("  Korrelation Rauschfaktor ~ Querabw. Fahrt: %.2f, ~ Welligkeit: %.2f" % (
        np.corrcoef(A["noise"], A["amp_fahrt_mm"])[0, 1], np.corrcoef(A["noise"], A["welligkeit_mm"])[0, 1]))
    for lo, hi in ((0, 0.2), (0.2, 0.6), (0.6, 1.01)):
        m = (A["noise"] >= lo) & (A["noise"] < hi)
        if m.any():
            print("  Rauschfaktor %.1f-%.1f (%d): Fahrt %.1f mm, Aufnahme %.1f mm, Gleichlauf %.2f, Welligkeit %.1f mm" % (
                lo, hi, m.sum(), np.median(A["amp_fahrt_mm"][m]), np.median(A["amp_aufn_mm"][m]),
                np.median(A["gleichlauf"][m]), np.median(A["welligkeit_mm"][m])))
