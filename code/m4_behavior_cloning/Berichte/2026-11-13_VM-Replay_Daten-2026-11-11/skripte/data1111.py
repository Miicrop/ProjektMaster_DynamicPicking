"""Aufnahme 11.11. gegen den Trainingsdatensatz 2026-11-09: Bedingungen und Lagen."""
import json, glob, os, collections
import numpy as np

ROOT = r"E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning"
os.chdir(ROOT)
exp = json.load(open("datasets/2026-11-09/meta/bc_export.json"))
tc = json.load(open("checkpoints/2026-11-09/train_config.json"))
val = set(tc["val_episodes"])
print("export episode entry:", exp["episodes"][0])

KEYS = ["light", "camera_pose", "object_note", "sequence_file", "layout_mode", "noise_scale_mode", "tool"]


def load(folder):
    rows = []
    for d in sorted(glob.glob(os.path.join(folder, "ep_*"))):
        try:
            m = json.load(open(os.path.join(d, "meta.json")))
        except OSError:
            continue
        md = m["metadata"]
        rows.append(dict(dir=d.replace("\\", "/"), disc=m["discarded"], len=m["length"], block=md.get("block"),
                         xy=md.get("object_xy_m"), yaw=md.get("object_yaw_deg"),
                         pick=md.get("points", {}).get("PICK", {}).get("pose_quat"),
                         j6=(md.get("points", {}).get("PICK", {}).get("joints") or [None] * 6)[5],
                         **{k: str(md.get(k)) for k in KEYS}))
    return rows


train_rows, val_rows = [], []
for e in exp["episodes"]:
    md = e["metadata"]
    r = dict(dir=e["source"] + "/" + e["source_dir"], block=md.get("block"), xy=md.get("object_xy_m"),
             yaw=md.get("object_yaw_deg"), pick=md.get("points", {}).get("PICK", {}).get("pose_quat"),
             j6=(md.get("points", {}).get("PICK", {}).get("joints") or [None] * 6)[5],
             **{k: str(md.get(k)) for k in KEYS})
    (val_rows if e["episode_index"] in val else train_rows).append(r)
print("Training/Val:", len(train_rows), len(val_rows))

new = load("data/2026-11-11")
print("\n11.11.: Episoden", len(new), "verworfen", sum(r["disc"] for r in new),
      "Laenge median", np.median([r["len"] for r in new]))
for k in KEYS:
    print("%-16s train %s" % (k, dict(collections.Counter(r[k] for r in train_rows))))
    print("%-16s 11.11 %s" % ("", dict(collections.Counter(r[k] for r in new))))

def yaw_mod(a):
    return a % 180.0

T = np.array([r["xy"] for r in train_rows if r["xy"]])
TY = np.array([yaw_mod(r["yaw"]) for r in train_rows if r["xy"]])
blocks = collections.OrderedDict()
for r in new:
    blocks.setdefault(r["block"], []).append(r)
print("\nObjektlagen 11.11.:", len(blocks))
res = []
for b, rs in blocks.items():
    r = rs[0]
    if not r["xy"]:
        continue
    d = np.linalg.norm(T - np.asarray(r["xy"]), axis=1) * 1000
    dy = np.abs(((TY - yaw_mod(r["yaw"])) + 90) % 180 - 90)
    i = int(np.argmin(d))
    # naechste Trainingslage mit aehnlicher Drehung (<15 Grad)
    m = dy < 15
    d_sim = float(d[m].min()) if m.any() else None
    res.append(dict(block=b, n=len(rs), x=round(r["xy"][0] * 1000), y=round(r["xy"][1] * 1000), yaw=r["yaw"],
                    j6=None if r["j6"] is None else round(r["j6"], 2),
                    next_mm=round(float(d[i])), next_dyaw=round(float(dy[i])),
                    next_sim_yaw_mm=None if d_sim is None else round(d_sim)))
for x in res:
    print(x)
nm = np.array([x["next_mm"] for x in res])
print("naechste Trainingslage xy [mm]: median %.0f, max %.0f" % (np.median(nm), nm.max()))
X = np.array([x["x"] for x in res]); Y = np.array([x["y"] for x in res])
print("x %d..%d  y %d..%d ; Training x %.0f..%.0f y %.0f..%.0f" % (X.min(), X.max(), Y.min(), Y.max(),
      T[:, 0].min() * 1000, T[:, 0].max() * 1000, T[:, 1].min() * 1000, T[:, 1].max() * 1000))
json.dump(dict(blocks=res, train_xy=T.tolist(), train_yaw=TY.tolist()),
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data1111.json"), "w"), indent=1)
