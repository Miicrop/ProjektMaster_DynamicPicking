"""Vergleich der Fahrtgruppen (Licht, Kamera, Tag) -- Kennzahlen je Gruppe als Markdown-Tabelle."""
import json, sys
from pathlib import Path
import numpy as np

R = Path(r"E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning\checkpoints\2026-11-09\policy\rollouts")
GRUPPEN = [
    ("11.11., neuer Tag", "aus", "stark gedreht", "2026-11-13_vm_replay_daten-2026-11-11", lambda r: not str(r["block"]).startswith("Test")),
    ("11.11., Test-Lagen", "an", "gedreht", "2026-11-13_vm_replay_daten-2026-11-11", lambda r: str(r["block"]).startswith("Test")),
    ("Val 03.11.", "an", "nominal, leicht gedreht", "2026-11-13_vm_replay_val-2026-11-03_licht-an", None),
    ("Val 09.11.", "aus", "stark gedreht", "2026-11-13_vm_replay_val-2026-11-09_licht-aus", None),
    ("Val 02.11.", "aus", "nominal", "2026-11-13_vm_replay_val-2026-11-02_licht-aus", None),
]
print("| Gruppe | Licht | Kamera | Fahrten | nächste Annäherung median | ≤ 10 mm | Greif-xy beim Schließen median | unter Tisch | tiefer als −10 mm | ServoGuard-Abbruch | Welligkeit median |")
print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
out = []
for name, licht, kamera, d, flt in GRUPPEN:
    p = R / d / "auswertung.json"
    if not p.exists():
        continue
    rows = json.loads(p.read_text(encoding="utf-8"))
    sw = {r["lauf"]: r for r in json.loads((R / d / "schwingen.json").read_text(encoding="utf-8"))} if (R / d / "schwingen.json").exists() else {}
    if flt:
        rows = [r for r in rows if flt(r)]
    n = len(rows)
    A = lambda k: np.array([r[k] for r in rows if r[k] is not None], float)
    near, gx, mc = A("nearest_mm"), A("grasp_xy_mm"), A("min_clear_mm")
    ab = sum(r["stop"].startswith("abgelehnt") for r in rows)
    wl = np.median([sw[r["lauf"]]["welligkeit_mm"] for r in rows if r["lauf"] in sw]) if sw else float("nan")
    print("| %s | %s | %s | %d | %.1f mm | %d %% | %.1f mm | %d %% | %d %% | %d %% | %.1f mm |" % (
        name, licht, kamera, n, np.median(near), round(100 * (near <= 10).mean()), np.median(gx),
        round(100 * (mc < 0).mean()), round(100 * (mc < -10).mean()), round(100 * ab / n), wl))
