#!/usr/bin/env bash
# Variante C (nur Anflug + Griff): Export sobald Export D fertig ist (CPU), Training
# nach der Kette A/B/D (GPU). Aufruf aus m4_behavior_cloning.
set -u
P="E:/Enviroments/bc_env/Scripts/python.exe"
V=Berichte/Versuchsreihe_Policy-Varianten
D="data/2026-11-02 data/2026-11-03 data/2026-11-09 data/2026-11-11"

until [ -f datasets/var_D/meta/bc_export.json ]; do sleep 60; done
if [ ! -f datasets/var_C/meta/bc_export.json ]; then
  echo "$(date '+%F %T') Export C"
  $P tools/export_variante.py --data $D --ohne-lagen $V/testlagen.json --abschneiden-nach 3 \
    --out datasets/var_C > $V/logs/export_C.log 2>&1 || { echo "Export C gescheitert"; exit 1; }
fi
until grep -q "Kette fertig" $V/logs/kette_ABD.log 2>/dev/null; do sleep 60; done
if [ ! -f checkpoints/var_C/policy/bc_policy.json ]; then
  echo "$(date '+%F %T') Training C"
  $P apps/train.py --dataset datasets/var_C --out checkpoints/var_C --steps 10000 --batch-size 128 \
    > $V/logs/train_C.log 2>&1 || { echo "Training C gescheitert"; exit 1; }
fi
echo "$(date '+%F %T') Kette C fertig"
