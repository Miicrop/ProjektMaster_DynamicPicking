"""Wann und wo geht der TCP unter die Tischflaeche? Phase, Tiefe, Zusammenhang mit Greiffehler."""
import sys, json
from pathlib import Path
import numpy as np

run = Path(sys.argv[1])
rows = json.loads((run / "auswertung.json").read_text(encoding="utf-8"))
A = lambda k: np.array([np.nan if r[k] is None else r[k] for r in rows], float)
mc, gs, ms = A("min_clear_mm"), A("grasp_step"), A("min_clear_step")
phase = np.where(ms < gs - 3, "vor", np.where(ms <= gs + 3, "am Griff", "nach"))
print("Fahrten", len(rows))
for lim in (3, 0, -5, -10, -20, -50):
    print("  tiefster Punkt < %+d mm: %d" % (lim, (mc < lim).sum()))
for ph in ("vor", "am Griff", "nach"):
    m = (phase == ph) & (mc < 0)
    print("  unter Tisch, Phase %-8s: %d (median %.1f mm)" % (ph, m.sum(), np.median(mc[m]) if m.any() else np.nan))
gc, dz = A("grasp_clear_mm"), A("grasp_dz_mm")
print("TCP ueber Tisch beim Schliessen: median %.1f, p10 %.1f, min %.1f mm (Aufnahme ~9 mm)" % (
    np.median(gc), np.percentile(gc, 10), np.min(gc)))
print("dz zum PICK beim Schliessen: median %.1f mm" % np.median(dz))
gx = A("grasp_xy_mm")
for lo, hi in ((0, 10), (10, 20), (20, 50), (50, 1e9)):
    m = (gx >= lo) & (gx < hi)
    print("  Greif-xy %3d-%-5s: %3d Fahrten, unter Tisch %d, tiefster Punkt median %.1f mm" % (
        lo, "" if hi > 1e6 else str(int(hi)), m.sum(), (mc[m] < 0).sum(), np.median(mc[m]) if m.any() else np.nan))
stops = {}
for r in rows:
    stops[r["stop"].split(":")[0]] = stops.get(r["stop"].split(":")[0], 0) + 1
print("Stopp:", stops)
ye = A("grasp_yaw_err_deg")
print("Drehfehler beim Greifen: median %.1f, p90 %.1f Grad, >20 Grad: %d" % (np.nanmedian(ye), np.nanpercentile(ye, 90), (ye > 20).sum()))
