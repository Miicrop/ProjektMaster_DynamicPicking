"""Eckdaten der Aufnahme 11.11. fuer das Protokoll."""
import json, glob, os, collections
import numpy as np

os.chdir(r"E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning")
lens, disc, noise, rep, over = [], [], [], collections.Counter(), []
for f in sorted(glob.glob("data/2026-11-11/ep_*/meta.json")):
    m = json.load(open(f, encoding="utf-8"))
    md = m["metadata"]
    lens.append(m["length"])
    if m["discarded"]:
        disc.append((os.path.basename(os.path.dirname(f)), md.get("block"), m["discard_reason"]))
    noise.append(md.get("noise_scale") or 0)
    rep[md.get("repeat_index")] += 1
    over.append(1e3 * (md.get("pick_over_table_m") or 0))
print("Episoden", len(lens), "Laenge median/min/max", np.median(lens), min(lens), max(lens))
print("verworfen", disc)
print("Rauschfaktor min/median/max", np.round(np.percentile(noise, [0, 50, 100]), 2))
print("Wiederholungsindex", dict(rep))
print("PICK ueber Tisch [mm] min/median/max", np.round(np.percentile(over, [0, 50, 100]), 1))
a = json.load(open("data/2026-11-11/ep_00000/meta.json", encoding="utf-8"))["metadata"]["recorded_at"]
b = json.load(open(sorted(glob.glob("data/2026-11-11/ep_*/meta.json"))[-1], encoding="utf-8"))["metadata"]["recorded_at"]
print("Zeitraum", a, "bis", b)
