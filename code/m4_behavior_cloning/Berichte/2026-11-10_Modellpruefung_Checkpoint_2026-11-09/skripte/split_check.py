"""Prueft die Train/Val-Aufteilung von checkpoints/2026-11-09 auf Lagen-Leck."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

root = Path(sys.argv[1])
exp = json.loads((root / "datasets/2026-11-09/meta/bc_export.json").read_text(encoding="utf-8"))
cfg = json.loads((root / "checkpoints/2026-11-09/train_config.json").read_text(encoding="utf-8"))
eps = exp["episodes"]
print("Episoden im Export:", len(eps))
print("Schluessel je Episode:", sorted(eps[0].keys()))
md0 = eps[0].get("metadata") or {}
print("Metadaten-Schluessel:", sorted(md0.keys()))
val = set(cfg["val_episodes"])


def key(md, *names):
    return tuple(md.get(n) for n in names)


rows = []
for i, ep in enumerate(eps):
    md = ep.get("metadata") or {}
    rows.append(dict(i=i, src=ep.get("source") or ep.get("path") or ep.get("episode_dir"),
                     session=md.get("session"), block=md.get("block"),
                     group=md.get("repeat_group"), layout=md.get("layout_index"),
                     variant=md.get("variant_index"), light=md.get("light"),
                     cam=md.get("camera_pose"), obj=md.get("object_note"),
                     pose=md.get("object_pose"), val=i in val))

print("\nSessions:", Counter(r["session"] for r in rows))
print("Gruppen:", len({r["group"] for r in rows}), " Bloecke (session,block):",
      len({(r["session"], r["block"]) for r in rows}))
print("Licht:", Counter(r["light"] for r in rows))
print("Kamera:", Counter(r["cam"] for r in rows))
print("Objekt:", Counter(r["obj"] for r in rows))
print("layout/variant:", Counter((r["layout"], r["variant"]) for r in rows).most_common(8))

blocks_val = defaultdict(set)
for r in rows:
    blocks_val[(r["session"], r["block"])].add(r["val"])
mixed = [b for b, s in blocks_val.items() if len(s) == 2]
print("\nBloecke mit Episoden in Train UND Val:", len(mixed), mixed[:10])
vb = sorted(b for b, s in blocks_val.items() if s == {True})
print("Reine Val-Bloecke:", len(vb), vb)

# Objektlage: geteachter PICK-Punkt, falls vorhanden
pk = [r for r in rows if r["pose"]]
print("\nEpisoden mit object_pose:", len(pk))
if pk:
    print("Beispiel object_pose:", json.dumps(pk[0]["pose"])[:300])
