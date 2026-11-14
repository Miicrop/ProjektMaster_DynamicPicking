"""summary.json fuer einen abgebrochenen infer.py-Lauf aus Konsolenausgabe + rollout_XXX.npz nachbauen.

Nur die Felder, die eval_stufe2.py / schwingen.py brauchen. Fahrt i gehoert zur
i-ten Episode der --replay-episode-Liste (wie in infer.py).
Aufruf: summary_aus_log.py <rollout-ordner> <log> <aufnahme> <episodenliste>
"""
import json
import re
import sys
from pathlib import Path

run, log, data, liste = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
episodes = [int(x) for x in liste.split(",")]
text = log.read_text(encoding="utf-8", errors="replace").splitlines()
res = {}
for k, line in enumerate(text):
    m = re.match(r"Fahrt (\d+): (ERFOLG|kein Erfolg) -- (\d+) Takte, .*?, ([^,]+(?:: [^,]+)?), Vorhersage ([\d.]+) ms, "
                 r"Overruns (\d+), gekappt (\d+)", line)
    if not m:
        continue
    i = int(m.group(1))
    stop = m.group(4).strip()
    stop = re.sub(r"^Bahn p95 [\d.]+ mm, ", "", stop)
    cmp = {}
    if k + 1 < len(text) and "Vergleich mit der Aufnahme" in text[k + 1]:
        v = text[k + 1]
        g = re.search(r"Greifpunkt ([\d.]+) mm \(([+-]?\d+) Takte", v)
        p = re.search(r"p95 ([\d.]+) mm / max", v)
        e = re.search(r"Ende ([\d.]+) mm", v)
        cmp = dict(grasp_err_mm=float(g.group(1)) if g else None,
                   grasp_step_offset=int(g.group(2)) if g else None,
                   path_dev_mm_p95=float(p.group(1)) if p else None,
                   end_err_mm=float(e.group(1)) if e else None)
    res[i] = dict(episode=i, steps=int(m.group(3)), stop_reason=stop, guard_rejections=int(stop.startswith("abgelehnt")),
                  limiter_clamped_steps=int(m.group(7)), pacer_overruns=int(m.group(6)),
                  predict_ms_median=float(m.group(5)), ensemble_spread_p95_rad=float("nan"),
                  replay=dict(root=data, episode=episodes[i], **cmp))
eps = [res[i] for i in sorted(res) if (run / ("rollout_%03d.npz" % i)).exists()]
(run / "summary.json").write_text(json.dumps(dict(nachgebaut_aus=str(log), episodes=eps), indent=1), encoding="utf-8")
print("%d Fahrten -> %s" % (len(eps), run / "summary.json"))
