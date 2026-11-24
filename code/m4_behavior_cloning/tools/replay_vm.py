"""VM-Replay: Policy faehrt in der VM, sieht dabei die ANLAGEN-Bilder (AP 5).

Geschlossener Regelkreis ohne Anlage. Die VM hat keine Kamera und kein
Objekt -- deshalb bekommt die Policy je Takt die Bilder der aufgezeichneten
Anlagen-Episode, deren TCP-Position der aktuellen am naechsten liegt (nur
Frames mit gleichem Greiferzustand, Suche vorwaerts gerichtet). Protokoll
der Entstehung: Berichte/2026-11-10_Modellpruefung_Checkpoint_2026-11-09/.
Weicht die Policy ab, sieht sie die Bilder der naechstgelegenen Stelle der
Demo -- das ist eine Naeherung, kein echtes Bild aus der neuen Stellung.

Warum nicht offline (Teacher Forcing): Befund 2026-10-29 -- nahe PICK verraet
der Zustand das Ziel, der Offline-Fehler sagt fast nichts ueber unbekannte
Lagen. Nur der geschlossene Kreis zeigt, ob die Policy aus den BILDERN zur
Lage findet.

Tool-Versatz: Die VM hat kein Tool hinterlegt, ihre "tool"-FK liefert den
Flansch. Die Anlagendaten sind im Tool-Frame (ZimmerLWR50). Der Versatz wird
beim Start aus der Aufzeichnucng selbst bestimmt (FK der VM fuer
aufgezeichnete Gelenkwinkel gegen den aufgezeichneten Zustand) und in
``read_state`` aufgeschlagen -- sonst liegt der Zustand ausserhalb der
Verteilung (Befund 2026-10-29: +197,5 mm Flansch-z).

Bewegt den Roboter NUR, wenn ``is_robot_in_simulation()`` True ist; das
erzwingt der Adapter (kein ``--real-robot`` hier).

    python tools/replay_vm.py --checkpoint checkpoints/2026-11-09/policy \
        --dataset datasets/2026-11-09 --val 8 --train 3
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import _bootstrap  # noqa: F401

import numpy as np

_APPS = Path(__file__).resolve().parent.parent / "apps"
sys.path.insert(0, str(_APPS))
import infer  # noqa: E402  (apps/infer.py)

from bc import geometry  # noqa: E402

#: Originale aus apps/infer.py -- je Fahrt wird neu eingehaengt, nie verschachtelt.
_ORIG_OPEN_ROBOT = infer.open_robot
_ORIG_CHECK = infer.check_against_recording
_ORIG_RUN_EPISODE = infer.run_episode

#: Suchfenster fuer den naechsten Frame: so weit zurueck/voraus (Frames)
#: relativ zum zuletzt gewaehlten. Verhindert Spruenge an Stellen der Bahn,
#: die sich in der Stellung aehneln (Start/Rueckweg).
WINDOW_BACK, WINDOW_AHEAD = 5, 40


class ReplayFrame(object):
    def __init__(self, image):
        self.image = image


class ReplayCapture(object):
    """Liefert das Anlagenbild zur naechstgelegenen Stellung der Demo."""

    def __init__(self, name, images, ref, trace=None):
        self.name = name
        self.images = images
        self.ref = ref
        self.trace = trace

    def start(self):
        return self

    def latest(self):
        return ReplayFrame(self.images[self.ref.current])

    def stop(self):
        pass


class Reference(object):
    """Haelt die Demo und waehlt je Zustand den Frame.

    Zuordnung ueber die TCP-POSITION (m), nicht ueber die Gelenkwinkel:
    Befund 2026-11-10 -- die Policy dreht das Handgelenk (Gelenk 6) anders
    als die Demo; ueber Gelenkwinkel landete der Bildzeiger dann an voellig
    falschen Stellen. Die Drehung wird separat ausgewertet (j6 am Greifpunkt).
    """

    def __init__(self, tcp_pos, gripper):
        self.pos = tcp_pos
        self.gripper = gripper
        self.current = 0
        self.trace = []

    def update(self, tcp_pos, gripper_closed):
        lo = max(0, self.current - WINDOW_BACK)
        hi = min(len(self.pos), self.current + WINDOW_AHEAD + 1)
        idx = np.arange(lo, hi)
        same = (self.gripper[idx] > 0.5) == bool(gripper_closed)
        if same.any():
            idx = idx[same]
        d = np.linalg.norm(self.pos[idx] - tcp_pos[None], axis=1)
        k = int(np.argmin(d))
        self.current = int(idx[k])
        self.trace.append((self.current, float(d[k])))


def fit_tool_offset(robot, states, n=8):
    """Versatz Flansch(VM) -> Tool(Anlage) im Flansch-Frame, aus der Aufzeichnung."""
    picks = np.linspace(0, len(states) - 1, n).astype(int)
    offs, qoffs = [], []
    for i in picks:
        joints = states[i, :6]
        p_rec, q_rec = states[i, 6:9], states[i, 9:13]
        vm = np.asarray(robot.fk(joints, frame="tool"), dtype=float)
        p_vm, q_vm = vm[:3], vm[3:7]
        offs.append(geometry.quat_to_matrix(q_vm).T @ (p_rec - p_vm))
        qo = geometry.quat_multiply(geometry.quat_conjugate(q_vm), q_rec)
        qoffs.append(qo if qo[0] >= 0 else -qo)
    offs, qoffs = np.array(offs), np.array(qoffs)
    off, qoff = offs.mean(axis=0), geometry.quat_normalize(qoffs.mean(axis=0))
    spread_mm = 1e3 * float(np.max(np.linalg.norm(offs - off, axis=1)))
    spread_deg = float(np.degrees(max(geometry.quat_angle_between(q, qoff) for q in qoffs)))
    return off, qoff, spread_mm, spread_deg


def install_patches(episode_dir, out_dir, holder):
    """Haengt Replay-Kameras und Tool-Korrektur in apps/infer.py ein."""
    arr = np.load(str(episode_dir / "arrays.npz"))
    states = arr["observation__state"].astype(float)
    ref = Reference(states[:, 6:9], states[:, 13])
    images = {"wrist": arr["observation__images__wrist"],
              "scene": arr["observation__images__scene"]}
    holder.update(ref=ref, states=states)

    def start_cameras(mode, clock, seed=0, uvc_device=None, specs=None, cfgs=None):
        return [ReplayCapture(n, images[n], ref) for n in ("wrist", "scene")], cfgs

    real_open = _ORIG_OPEN_ROBOT

    def open_robot(kind, **kw):
        robot = real_open(kind, **kw)
        real_connect = robot.connect

        def connect(*a, **k):
            r = real_connect(*a, **k)
            if robot.in_simulation is not True:
                raise SystemExit("Kein Replay: is_robot_in_simulation() ist nicht True.")
            off, qoff, s_mm, s_deg = fit_tool_offset(robot, states)
            holder.update(offset=off, qoffset=qoff, offset_spread_mm=s_mm,
                          offset_spread_deg=s_deg)
            print("Tool-Versatz aus Aufzeichnung: %s mm (Streuung %.2f mm, %.3f Grad)"
                  % (np.round(1e3 * off, 1), s_mm, s_deg))
            real_read = robot.read_state

            def read_state():
                st = real_read()
                pose = np.asarray(st.tcp_quat, dtype=float)
                p = pose[:3] + geometry.quat_to_matrix(pose[3:7]) @ off
                q = geometry.quat_multiply(pose[3:7], qoff)
                st.tcp_quat = np.concatenate([p, q])
                return st

            robot.read_state = read_state
            return r

        robot.connect = connect
        return robot

    real_check = _ORIG_CHECK

    def check(info, args, robot_kind, cam_cfgs):
        # Kamera-Backend weicht hier ABSICHTLICH ab (Replay statt Daheng).
        return [p for p in real_check(info, args, robot_kind, cam_cfgs)
                if not p.startswith("Kamera-Backends")]

    def build_observation(robot, captures):
        # Wie infer.build_observation, aber der Bildindex folgt GENAU dem
        # Zustand dieser Beobachtung (der Watchdog-Thread liest auch Zustaende).
        state = robot.read_state()
        ref.update(np.asarray(state.tcp_quat, dtype=float)[:3], state.gripper_closed)
        obs = {"observation.state": infer.dataset.build_state(
            state.joints, state.tcp_quat,
            infer.config.GRIPPER_CLOSED if state.gripper_closed else infer.config.GRIPPER_OPEN)}
        for cap in captures:
            obs["observation.images.%s" % cap.name] = infer._to_schema_size(cap.latest().image)
        return obs, state

    real_run = _ORIG_RUN_EPISODE

    def run_episode(*a, **k):
        # infer.main waermt die Policy VOR der Fahrt an die Startstellung auf;
        # diese Beobachtung darf den Bildzeiger nicht verschieben.
        ref.current, ref.trace = 0, []
        return real_run(*a, **k)

    infer.run_episode = run_episode
    infer.start_cameras = start_cameras
    infer.open_robot = open_robot
    infer.check_against_recording = check
    infer.build_observation = build_observation


def evaluate(out_dir, episode, holder):
    """Greif-/Uebergabefehler gegen DIESE Demo (nicht gegen die feste Referenz)."""
    z = np.load(str(out_dir / "rollout_000.npz"))
    tcp, grip = z["tcp"], z["gripper_cmd"]
    states = holder["states"]
    rec_close = int(np.argmax(states[:, 13] > 0.5)) if (states[:, 13] > 0.5).any() else None
    rec_grasp = states[rec_close, 6:9] if rec_close is not None else None
    res = {"steps": int(len(tcp))}
    closed = np.flatnonzero(grip > 0.5)
    if len(closed) and rec_grasp is not None:
        g = tcp[closed[0], :3]
        res["grasp_step"] = int(closed[0])
        res["grasp_err_mm"] = float(1e3 * np.linalg.norm(g - rec_grasp))
        res["grasp_err_xy_mm"] = float(1e3 * np.linalg.norm(g[:2] - rec_grasp[:2]))
        res["grasp_dz_mm"] = float(1e3 * (g[2] - rec_grasp[2]))
        # Handgelenk am Greifpunkt gegen die Demo (Objektdrehung erkannt?)
        dj6 = float(z["joints"][closed[0], 5] - states[rec_close, 5])
        res["grasp_dj6_deg"] = float(np.degrees(dj6))
        res["grasp_dj6_mod180_deg"] = float(np.degrees((dj6 + np.pi / 2) % np.pi - np.pi / 2))
    else:
        res["grasp_step"] = None
    res["end_err_mm"] = float(1e3 * np.linalg.norm(z["final_tcp"][:3] - states[-1, 6:9]))
    res["z_min_mm"] = float(1e3 * tcp[:, 2].min())
    res["rec_z_min_mm"] = float(1e3 * states[:, 8].min())
    d = np.array([t[1] for t in holder["ref"].trace]) if holder["ref"].trace else np.array([0.0])
    res["replay_dist_p95_mm"] = float(1e3 * np.percentile(d, 95))
    res["replay_dist_max_mm"] = float(1e3 * d.max())
    s = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    ep = s["episodes"][0] if s["episodes"] else {}
    res.update(stop_reason=ep.get("stop_reason"), reached_end=ep.get("reached_end"),
               guard_rejections=ep.get("guard_rejections"), wall_s=ep.get("wall_s"),
               predict_ms_median=ep.get("predict_ms_median"))
    res["success"] = bool(res.get("grasp_err_mm") is not None and res["grasp_err_mm"] <= 10
                          and res["end_err_mm"] <= 10 and res["reached_end"])
    (out_dir / "replay_trace.json").write_text(json.dumps(
        {"episode_dir": str(episode), "frames": int(len(states)),
         "tool_offset_m": list(map(float, holder["offset"])),
         "tool_offset_spread_mm": holder["offset_spread_mm"],
         "trace": holder["ref"].trace}), encoding="utf-8")
    return res


def choose_episodes(dataset, train_config, n_val, n_train, seed, explicit=None):
    exp = json.loads((Path(dataset) / "meta" / "bc_export.json").read_text(encoding="utf-8"))
    cfg = json.loads(Path(train_config).read_text(encoding="utf-8"))
    val = set(cfg["val_episodes"])
    if explicit:
        return [("val" if i in val else "train", i, exp["episodes"][i]) for i in explicit]
    rng = np.random.default_rng(seed)
    first = {}
    for i, ep in enumerate(exp["episodes"]):
        g = ep["metadata"].get("repeat_group") or i
        first.setdefault((i in val, g), (i, ep))
    vals = [v for (isval, _), v in first.items() if isval]
    trains = [v for (isval, _), v in first.items() if not isval]
    pick_v = [vals[k] for k in sorted(rng.choice(len(vals), min(n_val, len(vals)), replace=False))]
    pick_t = [trains[k] for k in sorted(rng.choice(len(trains), min(n_train, len(trains)), replace=False))]
    return [("val", i, ep) for i, ep in pick_v] + [("train", i, ep) for i, ep in pick_t]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--checkpoint", required=True, help="<out>/policy oder <out>/checkpoints/step_*")
    ap.add_argument("--dataset", required=True, help="Datensatz des Trainings (fuer Split und Quellen)")
    ap.add_argument("--train-config", default=None, help="Default: <checkpoint>/../train_config.json")
    ap.add_argument("--val", type=int, default=8, help="so viele unbekannte Lagen")
    ap.add_argument("--train", type=int, default=3, help="so viele Trainingslagen")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--episodes", default=None,
                    help="statt Zufallsauswahl: Datensatz-Episoden, z. B. '506,412'")
    ap.add_argument("--out", default=None)
    ap.add_argument("--table-z", type=float, default=None,
                    help="an infer.py durchgereicht (Geofence-Tischhoehe)")
    args = ap.parse_args()

    ckpt = Path(args.checkpoint)
    run_dir = ckpt.parent if ckpt.name == "policy" else ckpt.parent.parent
    train_config = Path(args.train_config) if args.train_config else run_dir / "train_config.json"
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    out_root = Path(args.out) if args.out else run_dir / "rollouts" / ("%s_vm_replay_%s" % (stamp, ckpt.name))
    out_root.mkdir(parents=True, exist_ok=True)

    explicit = [int(x) for x in args.episodes.split(",")] if args.episodes else None
    plan = choose_episodes(args.dataset, train_config, args.val, args.train, args.seed, explicit)
    results = []
    for kind, idx, ep in plan:
        md = ep["metadata"]
        src = Path(ep["source"]) / ep["source_dir"]
        name = "%s_%s_%s_ep%03d" % (kind, md["session"], md["block"], idx)
        out = out_root / name
        print("\n=== %s: %s (Datensatz-Ep. %d, %s) ===" % (kind, src, idx, md.get("light")))
        holder = {}
        install_patches(src, out, holder)
        argv = ["infer.py", "--checkpoint", str(ckpt), "--robot", "neura", "--cameras", "sim",
                "--episodes", "1", "--out", str(out)]
        if args.table_z is not None:
            argv += ["--table-z", str(args.table_z)]
        sys.argv = argv
        t0 = time.time()
        try:
            infer.main()
            res = evaluate(out, src, holder)
        except SystemExit as exc:
            res = {"error": str(exc)}
        except Exception as exc:  # eine Fahrt darf die Reihe nicht beenden
            res = {"error": "%s: %s" % (type(exc).__name__, exc)}
        res.update(kind=kind, dataset_episode=idx, source=str(src), session=md["session"],
                   block=md["block"], light=md.get("light"), camera_pose=md.get("camera_pose"),
                   object_xy_m=md.get("object_xy_m"), object_yaw_deg=md.get("object_yaw_deg"),
                   seconds=time.time() - t0)
        results.append(res)
        print("-> %s" % json.dumps({k: res.get(k) for k in (
            "success", "grasp_err_mm", "grasp_dz_mm", "end_err_mm", "z_min_mm", "stop_reason", "error")}))

    report = {"checkpoint": str(ckpt), "dataset": args.dataset, "created": stamp,
              "note": "VM-Replay mit Anlagenbildern; VM-Ergebnis ist keine Anlagenmessung",
              "results": results}
    (out_root / "replay_summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                                  encoding="utf-8")
    print("\n%-5s %-11s %-5s %7s %7s %7s %7s %7s %7s  %s" % (
        "Art", "Session", "Block", "Greif", "dz", "dj6", "Ende", "z_min", "Bild_p95", "Stopp"))
    for r in results:
        print("%-5s %-11s %-5s %7s %7s %7s %7s %7s %7s  %s" % (
            r["kind"], r["session"], r["block"], _f(r.get("grasp_err_mm")), _f(r.get("grasp_dz_mm")),
            _f(r.get("grasp_dj6_deg")), _f(r.get("end_err_mm")), _f(r.get("z_min_mm")),
            _f(r.get("replay_dist_p95_mm")), r.get("stop_reason") or r.get("error")))
    print("-> %s" % (out_root / "replay_summary.json"))


def _f(v):
    return "-" if v is None else "%.1f" % v


if __name__ == "__main__":
    main()
