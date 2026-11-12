"""Aufnahmen wieder einspielen: Policy gegen die Aufzeichnung pruefen.

Zwei Stufen (Anwender 2026-11-12, "Inferenz in der VM mit den Laeufen von
gestern pruefen"):

1. **Offline** (:func:`open_loop`, apps/replay_check.py): je Takt Bilder UND
   Zustand der Aufnahme in die Policy, die vorhergesagte Action gegen die
   aufgezeichnete. Kein Roboter, keine VM, reproduzierbar. Zeigt, ob die
   Policy auf genau den Bildern, die sie kennen sollte, die Bahn trifft.

2. **Geschlossen in der VM** (apps/infer.py ``--replay``): die Kameras
   liefern die Bilder der Aufnahme (adapters/cam_replay.py), der Zustand
   kommt vom (VM-)Roboter, der die Actions der Policy faehrt. Danach
   :func:`compare_rollout` -- gefahrene gegen aufgezeichnete Bahn.
   Grenze: die Bilder reagieren nicht auf den Arm. Sie laufen je Takt um
   eins weiter (nicht nach Uhrzeit); weicht der Arm ab, sieht die Policy
   trotzdem die Bilder der Aufnahme.

Eingespielt werden die gespeicherten Arrays (schon 240x320, genau das, was
die Policy im Training sah) -- kein Video: Kompression wuerde die Bilder
veraendern.
"""

import json
from pathlib import Path

import numpy as np

from . import config, dataset
from .metrics import distance_to_path

#: Schluessel der Bilder in arrays.npz (Punkte als "__" gespeichert).
IMAGE_KEY = "observation__images__%s"


def read_index(root):
    path = Path(root) / "index.json"
    if not path.is_file():
        raise FileNotFoundError("%s fehlt -- kein Aufnahme-Ordner (apps/record.py)" % path)
    return json.loads(path.read_text(encoding="utf-8"))


def episode_dir(root, index):
    """Ordner der Episode ``index`` (Position im index.json)."""
    episodes = read_index(root)["episodes"]
    if not 0 <= int(index) < len(episodes):
        raise IndexError("Episode %s gibt es nicht (Aufnahme hat %d)" % (index, len(episodes)))
    return Path(root) / episodes[int(index)]["dir"]


def usable_episodes(root):
    """Indizes der nicht verworfenen Episoden (meta.json zaehlt, wie beim Export)."""
    out = []
    for i, entry in enumerate(read_index(root)["episodes"]):
        meta_path = Path(root) / entry["dir"] / "meta.json"
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not meta.get("discarded"):
            out.append(i)
    return out


def parse_episodes(text, root):
    """'3', '0,4,7', '2-5' oder 'alle' -> Liste von Indizes."""
    text = str(text).strip().lower()
    if text in ("alle", "all"):
        return usable_episodes(root)
    out = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def load_images(root, index, camera):
    """Bilder einer Kamera (N, H, W, 3) uint8 -- laedt nur dieses Array."""
    path = episode_dir(root, index) / "arrays.npz"
    with np.load(path) as npz:
        key = IMAGE_KEY % camera
        if key not in npz.files:
            raise KeyError("Kamera '%s' fehlt in %s" % (camera, path))
        return npz[key]


def check_compatible(root, info):
    """Passt die Aufnahme zur Policy (Schema, Rate, Bildgroesse, Kameras)?

    ``info``: bc_policy.json. Rueckgabe: Liste von Problemen (leer = gut).
    """
    index = read_index(root)
    problems = []
    if index.get("schema_version") != info.get("schema_version"):
        problems.append("Schema Aufnahme v%s, Policy v%s"
                        % (index.get("schema_version"), info.get("schema_version")))
    if float(index.get("rate_hz", 0)) != float(info.get("rate_hz", 0)):
        problems.append("Rate Aufnahme %s Hz, Policy %s Hz"
                        % (index.get("rate_hz"), info.get("rate_hz")))
    missing = [c for c in info.get("cameras", []) if c not in index.get("cameras", [])]
    if missing:
        problems.append("Kameras %s fehlen in der Aufnahme (hat %s)"
                        % (missing, index.get("cameras")))
    if info.get("image_size_hw") and list(info["image_size_hw"]) != [config.IMAGE_HEIGHT,
                                                                       config.IMAGE_WIDTH]:
        problems.append("Bildgroesse Policy %s" % info["image_size_hw"])
    return problems


def observation_at(arrays, step, cameras):
    """Beobachtung des Takts ``step`` genau wie im Training (dataset-Schluessel)."""
    obs = {"observation.state": np.asarray(arrays["observation.state"][step], dtype=np.float32)}
    for cam in cameras:
        obs["observation.images.%s" % cam] = arrays["observation.images.%s" % cam][step]
    return obs


# --------------------------------------------------------------------------
# Stufe 1: offline
# --------------------------------------------------------------------------


def open_loop(executor, arrays, cameras, progress=None):
    """Spielt eine Episode Takt fuer Takt durch den Executor (synchron).

    ``executor``: policy.ChunkEnsembler/ChunkExecutor -- derselbe Weg wie in
    apps/infer.py, also inklusive Mitteln der Chunks.
    Rueckgabe: dict mit ``predicted`` (N, 7) und ``recorded`` (N, 7).
    """
    executor.reset()
    n = len(arrays["observation.state"])
    predicted = np.zeros((n, config.ACTION_DIM))
    for step in range(n):
        predicted[step] = executor.next_action(observation_at(arrays, step, cameras))
        if progress and step % 30 == 0:
            progress("    Takt %4d/%d" % (step, n))
    return {"predicted": predicted, "recorded": np.asarray(arrays["action"], dtype=float)}


def _switch_steps(gripper):
    g = np.asarray(gripper, dtype=float) > config.GRIPPER_THRESHOLD
    return [int(i) + 1 for i in np.flatnonzero(g[1:] != g[:-1])]


def summarize_open_loop(result):
    """Kennzahlen eines :func:`open_loop`-Laufs (Gelenke in Grad)."""
    pred, rec = np.asarray(result["predicted"]), np.asarray(result["recorded"])
    err = np.degrees(np.abs(pred[:, :6] - rec[:, :6]))
    per_step = err.max(axis=1)
    g_pred = pred[:, 6] > config.GRIPPER_THRESHOLD
    g_rec = rec[:, 6] > config.GRIPPER_THRESHOLD
    sw_pred, sw_rec = _switch_steps(pred[:, 6]), _switch_steps(rec[:, 6])
    offsets = [min((p - r for p in sw_pred), key=abs) if sw_pred else None for r in sw_rec]
    return {
        "steps": int(len(rec)),
        "joint_err_deg_median": float(np.median(per_step)),
        "joint_err_deg_p95": float(np.percentile(per_step, 95)),
        "joint_err_deg_max": float(per_step.max()),
        "joint_err_deg_max_step": int(per_step.argmax()),
        "joint_err_deg_p95_per_joint": [float(v) for v in np.percentile(err, 95, axis=0)],
        "gripper_agreement": float(np.mean(g_pred == g_rec)),
        "gripper_switch_recorded": sw_rec,
        "gripper_switch_predicted": sw_pred,
        "gripper_switch_offset_steps": offsets,
    }


# --------------------------------------------------------------------------
# Stufe 2: geschlossen (VM)
# --------------------------------------------------------------------------


def compare_rollout(log, arrays):
    """Gefahrene Bahn (apps/infer.py run_episode) gegen die Aufnahme.

    Zwei Sichten: Abstand zur aufgezeichneten Bahn (zeitunabhaengig -- trifft
    der Arm die Bahn?) und Abstand Takt fuer Takt (laeuft er auch im selben
    Tempo?). Referenz ist die IDEALE TCP-Bahn (aux.pose_ideal): die Aufnahmen
    mit Rauschinjektion weichen in der Ist-Bahn absichtlich ab.
    Positionen in mm, Gelenke in Grad.
    """
    tcp = np.asarray(log["tcp"], dtype=float)
    joints = np.asarray(log["joints"], dtype=float)
    state = np.asarray(arrays["observation.state"], dtype=float)
    ideal = np.asarray(arrays.get("aux.pose_ideal", state[:, 6:13]), dtype=float)[:, :3]
    rec_joints = state[:, :6]
    out = {"steps_rollout": int(len(tcp)), "steps_recording": int(len(ideal))}
    if not len(tcp):
        return out
    dev = distance_to_path(tcp[:, :3], ideal)
    out["path_dev_mm_median"] = float(1e3 * np.median(dev))
    out["path_dev_mm_p95"] = float(1e3 * np.percentile(dev, 95))
    out["path_dev_mm_max"] = float(1e3 * dev.max())
    n = min(len(tcp), len(ideal))
    step_err = np.linalg.norm(tcp[:n, :3] - ideal[:n], axis=1)
    out["step_err_mm_median"] = float(1e3 * np.median(step_err))
    out["step_err_mm_p95"] = float(1e3 * np.percentile(step_err, 95))
    jerr = np.degrees(np.abs(joints[:n] - rec_joints[:n])).max(axis=1)
    out["joint_err_deg_p95"] = float(np.percentile(jerr, 95))
    final = np.asarray(log.get("final_tcp", tcp[-1]), dtype=float)[:3]
    out["end_err_mm"] = float(1e3 * np.linalg.norm(final - ideal[-1]))

    # Greifpunkt: erster Schliessbefehl in Fahrt und Aufnahme
    rec_close = [s for s in _switch_steps(arrays["action"][:, 6])
                 if arrays["action"][s, 6] > config.GRIPPER_THRESHOLD]
    cmd = np.asarray(log.get("gripper_cmd", []), dtype=float)
    roll_close = [s for s in _switch_steps(cmd) if cmd[s] > config.GRIPPER_THRESHOLD]
    if rec_close and roll_close:
        r, p = rec_close[0], roll_close[0]
        # wie metrics.evaluate_rollout: gemessen einen Takt nach dem Befehl
        at_roll = tcp[min(p + 1, len(tcp) - 1), :3]
        at_rec = ideal[min(r + 1, len(ideal) - 1)]
        out["grasp_err_mm"] = float(1e3 * np.linalg.norm(at_roll - at_rec))
        out["grasp_step_offset"] = int(p - r)
    else:
        out["grasp_err_mm"] = None
        out["grasp_step_offset"] = None
    return out


def format_rollout_comparison(cmp):
    def mm(key):
        return "-" if cmp.get(key) is None else "%.1f mm" % cmp[key]
    return ("Vergleich mit der Aufnahme: Bahnabstand median %s / p95 %s / max %s, "
            "Takt fuer Takt p95 %s, Greifpunkt %s (%s Takte versetzt), Ende %s, "
            "Takte %d statt %d"
            % (mm("path_dev_mm_median"), mm("path_dev_mm_p95"), mm("path_dev_mm_max"),
               mm("step_err_mm_p95"), mm("grasp_err_mm"),
               "-" if cmp.get("grasp_step_offset") is None else "%+d" % cmp["grasp_step_offset"],
               mm("end_err_mm"), cmp.get("steps_rollout", 0), cmp.get("steps_recording", 0)))


def load_arrays(root, index):
    """Alle Arrays einer Episode (dataset-Schluessel mit Punkten)."""
    return dataset.load_episode(root, index).arrays
