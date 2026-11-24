"""Abgebrochenen VM-Lauf mit dem Nachlauf zusammenfuehren.

Teil 1: <ordner> mit rollout_000..k-1 und (nachgebauter) summary.json.
Teil 2: <rest-ordner> aus einem zweiten infer-Lauf ueber die restlichen
Episoden der Liste (Fahrt 0 dort = Fahrt k gesamt). Die Dateien von Teil 2
werden mit versetzter Nummer nach <ordner> kopiert, summary.json vereint.
Aufruf: rollouts_zusammen.py <ordner> <rest-ordner>
"""
import json
import shutil
import sys
from pathlib import Path

run, rest = Path(sys.argv[1]), Path(sys.argv[2])
a = json.loads((run / "summary.json").read_text(encoding="utf-8"))
b = json.loads((rest / "summary.json").read_text(encoding="utf-8"))
k = len(a["episodes"])
assert sorted(e["episode"] for e in a["episodes"]) == list(range(k)), "Teil 1 nicht lueckenlos"
for e in b["episodes"]:
    src = rest / ("rollout_%03d.npz" % e["episode"])
    e = dict(e, episode=e["episode"] + k)
    shutil.copy2(src, run / ("rollout_%03d.npz" % e["episode"]))
    a["episodes"].append(e)
a["zusammengefuehrt"] = dict(teil1=k, teil2=len(b["episodes"]), rest=str(rest))
(run / "summary.json").write_text(json.dumps(a, indent=1, ensure_ascii=False), encoding="utf-8")
print("%d + %d Fahrten -> %s" % (k, len(b["episodes"]), run / "summary.json"))
