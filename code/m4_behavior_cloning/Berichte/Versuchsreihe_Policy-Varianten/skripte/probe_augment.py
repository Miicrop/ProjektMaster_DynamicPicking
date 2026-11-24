"""Sichtprobe --licht-augment: ein Beispiel aus dem Datensatz mehrfach augmentiert.

Aufruf: probe_augment.py <datensatz> <ausgabe-png>
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(r"E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning")
sys.path.insert(0, str(ROOT / "apps"))
import _bootstrap  # noqa: F401,E402
import train  # noqa: E402
import torch  # noqa: E402

from lerobot.datasets import LeRobotDataset  # noqa: E402

root = ROOT / sys.argv[1]
deltas = {"observation.images.scene": [-1 / 15, 0.0], "observation.images.wrist": [-1 / 15, 0.0]}
plain = LeRobotDataset("local/probe", root=root, episodes=[0], delta_timestamps=deltas)
aug = LeRobotDataset("local/probe", root=root, episodes=[0], delta_timestamps=deltas,
                     image_transforms=train.licht_transforms())
i = 60
a0 = plain[i]
imgs = [a0]
torch.manual_seed(0)
for _ in range(5):
    imgs.append(aug[i])
for key in ("observation.images.scene", "observation.images.wrist"):
    x = imgs[1][key]
    print(key, tuple(x.shape), x.dtype, "min %.3f max %.3f" % (float(x.min()), float(x.max())),
          "| Stapel gleich behandelt:",
          bool(torch.allclose(imgs[1][key][0] / (a0[key][0] + 1e-3), imgs[1][key][1] / (a0[key][1] + 1e-3), atol=0.5)))
    print("  Helligkeit roh %.3f, augmentiert %s" % (float(a0[key].mean()),
          ", ".join("%.3f" % float(m[key].mean()) for m in imgs[1:])))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, ax = plt.subplots(2, 6, figsize=(18, 5))
for j, key in enumerate(("observation.images.scene", "observation.images.wrist")):
    for k, it in enumerate(imgs):
        ax[j, k].imshow(np.clip(it[key][-1].permute(1, 2, 0).numpy(), 0, 1))
        ax[j, k].set_title("roh" if k == 0 else "augmentiert %d" % k, fontsize=9)
        ax[j, k].axis("off")
fig.suptitle("--licht-augment: %s" % train.LICHT_AUGMENT, fontsize=9)
fig.tight_layout()
fig.savefig(sys.argv[2], dpi=90)
print("Bild:", sys.argv[2])
