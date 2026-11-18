#!/usr/bin/env bash
# Variante C' = C auf dem alten Datensatz (02./03./09.11., ohne 11.11.):
# Export mit --abschneiden-nach 3, Training 10 000 Schritte (Seed 0), VM-Replay T60
# mit --transport-geplant. Trennt den Effekt von C vom Effekt der Daten vom 11.11.
# Aufruf aus m4_behavior_cloning.
set -u
P="E:/Enviroments/bc_env/Scripts/python.exe"
V=Berichte/Versuchsreihe_Policy-Varianten
S=$V/skripte
D="data/2026-11-02 data/2026-11-03 data/2026-11-09"
CK=checkpoints/C2_nur_griff_ohne_1111
T60=$($P -c "import json;print(','.join(map(str,json.load(open('$V/testlagen.json'))['T60'])))")
vm_ok() {
  $P -c "
import os,sys;sys.path.insert(0,'tools');import _bootstrap
from bc.adapters import open_robot
r=open_robot('neura');r.connect(power_on=False);ok=r.in_simulation is True;r.close();sys.exit(0 if ok else 1)" > /dev/null 2>&1
}

if [ ! -f datasets/var_C2/meta/bc_export.json ]; then
  echo "$(date '+%F %T') Export C2"
  $P tools/export_variante.py --data $D --abschneiden-nach 3 --out datasets/var_C2 \
    > $V/logs/export_C2.log 2>&1 || { echo "Export C2 gescheitert"; exit 1; }
fi
if [ ! -f $CK/policy/bc_policy.json ]; then
  echo "$(date '+%F %T') Training C2"
  $P apps/train.py --dataset datasets/var_C2 --out $CK --steps 10000 --batch-size 128 \
    --num-workers 6 > $V/logs/train_C2.log 2>&1 || { echo "Training C2 gescheitert"; exit 1; }
fi
out=$CK/policy/rollouts/vm_T60
if [ ! -f $out/summary.json ]; then
  until vm_ok; do echo "$(date '+%F %T') warte auf VM"; sleep 120; done
  echo "$(date '+%F %T') VM-Replay C2"
  GEOFENCE=alt $P $S/stufe2_vm.py --robot neura --checkpoint $CK/policy --replay data/2026-11-11 \
    --replay-episode $T60 --transport-geplant --out $out > $V/logs/vm_C2.log 2>&1
  $P $S/eval_stufe2.py $out > /dev/null 2>&1
  $P $S/schwingen.py $out > /dev/null 2>&1
fi
echo "$(date '+%F %T') Kette C2 fertig"
