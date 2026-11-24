"""Tempo-Profil der Policy (Sim-Testfahrten) gegen Abstand zum Greifpunkt, verglichen mit dem Experten.
Pendeln = Tempo-Umkehrungen (schneller/langsamer im Wechsel, > 5 mm/s) im Bereich 30-90 mm vor dem Griff."""
import glob, json, sys
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")
L = {l["id"]: l for l in json.load(open("bc/sim_mujoco/testlagen_v1.json"))["lagen"]}
bins = [(0, 10), (10, 20), (20, 30), (30, 45), (45, 60), (60, 80), (80, 120)]
def profil(tcp, pick):
    d = np.linalg.norm(tcp - pick, axis=1) * 1000
    v = np.linalg.norm(np.diff(tcp, axis=0), axis=1) * 15 * 1000
    return d[1:], v
def pendeln(d, v):
    m = (d > 30) & (d < 90)
    vv = v[m]
    if len(vv) < 5: return 0
    dv = np.diff(vv); dv = dv[np.abs(dv) > 5]
    return int(np.sum(np.diff(np.sign(dv)) != 0))
def report(name, prof):
    out = [name]
    for b in bins:
        vals = np.concatenate([v[(d >= b[0]) & (d < b[1])] for d, v in prof]) if prof else np.array([])
        out.append(f"{b[0]}-{b[1]}: {np.median(vals):4.0f}" if len(vals) else f"{b[0]}-{b[1]}: -")
    pe = [pendeln(d, v) for d, v in prof]
    print(" | ".join(out) + f" || Pendeln 30-90 mm: median {np.median(pe):.0f}, p90 {np.percentile(pe,90):.0f} Umkehrungen")
print("Tempo TCP (mm/s) nach Abstand zum Greifpunkt (mm)")
for m in sys.argv[1:]:
    if m.startswith("experte:"):
        prof = []
        for f in sorted(glob.glob(m.split(":", 1)[1]))[:150]:
            z = np.load(f); st, act = z["observation__state"], z["action"]
            c = np.flatnonzero(act[:, 6] > 0.5)
            if not len(c): continue
            c = int(c[0]); prof.append(profil(st[:c + 1, 6:9], st[c, 6:9]))
        report(m.split(":")[1].split("/")[1][:28] + " (Experte)", prof); continue
    d = json.load(open(f"data_sim_mujoco/rollouts_{m}/sim_auswertung.json"))
    prof = []
    for i, f in enumerate(d["fahrten"]):
        z = np.load(f"data_sim_mujoco/rollouts_{m}/rollout_{i:03d}.npz")
        prof.append(profil(z["tcp"][:, :3], np.array(L[f["lage"]]["pick_pose"][:3])))
    report(m, prof)
