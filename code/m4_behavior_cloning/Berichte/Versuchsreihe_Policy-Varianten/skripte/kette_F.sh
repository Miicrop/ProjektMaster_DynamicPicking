#!/usr/bin/env bash
# Variante F = A + --licht-augment (Datensatz var_A, Seed 0, 10 000 Schritte), danach
# VM-Replay T60 wie A. Startet erst, wenn die Kette C2 (inkl. VM) fertig ist.
# Wird F wieder so genau wie der alte Checkpoint, lag die Verschlechterung durch die
# Daten vom 11.11. am Licht. Aufruf aus m4_behavior_cloning.
set -u
P="E:/Enviroments/bc_env/Scripts/python.exe"
V=Berichte/Versuchsreihe_Policy-Varianten
S=$V/skripte
CK=checkpoints/F_licht_augment
T60=$($P -c "import json;print(','.join(map(str,json.load(open('$V/testlagen.json'))['T60'])))")
vm_ok() {
  $P -c "
import os,sys;sys.path.insert(0,'tools');import _bootstrap
from bc.adapters import open_robot
r=open_robot('neura');r.connect(power_on=False);ok=r.in_simulation is True;r.close();sys.exit(0 if ok else 1)" > /dev/null 2>&1
}

until grep -qE "Kette C2 fertig|gescheitert" $V/logs/kette_C2.log 2>/dev/null; do sleep 60; done
if [ ! -f $CK/policy/bc_policy.json ]; then
  echo "$(date '+%F %T') Training F (A + Licht-Augmentierung)"
  $P apps/train.py --dataset datasets/var_A --out $CK --steps 10000 --batch-size 128 --licht-augment \
    --num-workers 6 > $V/logs/train_F.log 2>&1 || { echo "Training F gescheitert"; exit 1; }
fi
out=$CK/policy/rollouts/vm_T60
if [ ! -f $out/summary.json ]; then
  until vm_ok; do echo "$(date '+%F %T') warte auf VM"; sleep 120; done
  echo "$(date '+%F %T') VM-Replay F"
  GEOFENCE=alt $P $S/stufe2_vm.py --robot neura --checkpoint $CK/policy --replay data/2026-11-11 \
    --replay-episode $T60 --out $out > $V/logs/vm_F.log 2>&1
  $P $S/eval_stufe2.py $out > /dev/null 2>&1
  $P $S/schwingen.py $out > /dev/null 2>&1
fi
echo "$(date '+%F %T') Kette F fertig"
