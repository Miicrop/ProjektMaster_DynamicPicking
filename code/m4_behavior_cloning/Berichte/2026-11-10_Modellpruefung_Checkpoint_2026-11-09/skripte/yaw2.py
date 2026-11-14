import json, os, sys
import numpy as np
root = sys.argv[1]
sys.path.insert(0, root)
from bc import geometry
exp = json.load(open(os.path.join(root, "datasets/2026-11-09/meta/bc_export.json"), encoding="utf-8"))
tool, yaw, j6 = [], [], []
for ep in exp["episodes"]:
    s = np.load(os.path.join(root, ep["source"], ep["source_dir"], "arrays.npz"))["observation__state"]
    c = np.flatnonzero(s[:, 13] > 0.5)[0]
    R = geometry.quat_to_matrix(s[c, 9:13])
    tool.append(np.degrees(np.arctan2(R[1, 0], R[0, 0])))
    yaw.append(ep["metadata"]["object_yaw_deg"]); j6.append(np.degrees(s[c, 5]))
tool, yaw, j6 = map(np.array, (tool, yaw, j6))
for sign in (1, -1):
    r = (sign * tool - yaw + 90) % 180 - 90
    print("sign %+d: Werkzeug-yaw - Objekt-yaw (mod 180): median %.1f  p5 %.1f p95 %.1f" % (sign, np.median(r), np.percentile(r, 5), np.percentile(r, 95)))
# Mehrdeutigkeit: gleiche Objekt-yaw (+-5 Grad), j6-Spannweite
w = []
for y in range(0, 180, 10):
    m = np.abs((yaw - y + 90) % 180 - 90) < 5
    if m.sum() > 3: w.append((y, int(m.sum()), round(float(np.ptp(j6[m])), 0)))
print("j6-Spannweite je Objekt-yaw (+-5 Grad): ", w)
d360 = np.round(((tool - yaw) % 360)).astype(int) % 360
sess = np.array([ep["metadata"]["session"] for ep in exp["episodes"]])
for lo, hi in ((0, 90), (90, 181)):
    m = (yaw >= lo) & (yaw < hi)
    vals, cnt = np.unique(d360[m], return_counts=True)
    print("Objekt-yaw %3d-%3d: Werkzeug-yaw minus Objekt-yaw (mod 360) ->" % (lo, hi), dict(zip(vals.tolist(), cnt.tolist())))
m = (yaw < 90)
flip = d360 == 180
print("Flip-Anteil je Session (yaw<90):", {s: "%d/%d" % ((flip & m & (sess == s)).sum(), (m & (sess == s)).sum()) for s in np.unique(sess)})
# trennt der Flip sich nach j6-Grenze?
print("j6 bei Flip: %.0f..%.0f  ohne Flip (yaw<90): %.0f..%.0f" % (j6[flip].min(), j6[flip].max(), j6[m & ~flip].min(), j6[m & ~flip].max()))
xy = np.array([ep["metadata"]["object_pose"]["PICK"][:2] for ep in exp["episodes"]])
print("yaw<90, Flip je yaw-Band:")
for lo in range(0, 90, 15):
    mm = m & (yaw >= lo) & (yaw < lo + 15)
    print("  %2d-%2d Grad: Flip %d/%d" % (lo, lo + 15, (flip & mm).sum(), mm.sum()))
from collections import Counter
print("Flip je y-Band (yaw<90):", [(round(a, 2), "%d/%d" % ((flip & m & (xy[:, 1] >= a) & (xy[:, 1] < a + 0.05)).sum(), (m & (xy[:, 1] >= a) & (xy[:, 1] < a + 0.05)).sum())) for a in np.arange(-0.30, 0.0, 0.05)])
st = np.array([ep["metadata"].get("repeat_index") for ep in exp["episodes"]])
