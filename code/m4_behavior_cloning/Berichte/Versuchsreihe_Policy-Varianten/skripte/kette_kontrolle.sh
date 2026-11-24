#!/usr/bin/env bash
# Kontrolle Trainingsstreuung: alter Datensatz (Checkpoint 2026-11-09) mit Seed 1
# neu trainieren, dann VM-Replay T60 wie die Varianten. Liegt das Ergebnis bei
# ~15 mm statt ~11 mm, ist der Abstand A-D vs. 2026-11-09 Streuung zwischen
# Trainings und nicht Folge der Daten vom 11.11.
# Nebenbei: --num-workers 6 statt 4 (Geschwindigkeit des Datenladens).
# Aufruf aus m4_behavior_cloning.
set -u
P="E:/Enviroments/bc_env/Scripts/python.exe"
V=Berichte/Versuchsreihe_Policy-Varianten
S=$V/skripte
CK=checkpoints/kontrolle_2026-11-09_seed1
T60=$($P -c "import json;print(','.join(map(str,json.load(open('$V/testlagen.json'))['T60'])))")
vm_ok() {
  $P -c "
import os,sys;sys.path.insert(0,'tools');import _bootstrap
from bc.adapters import open_robot
r=open_robot('neura');r.connect(power_on=False);ok=r.in_simulation is True;r.close();sys.exit(0 if ok else 1)" > /dev/null 2>&1
}

if [ ! -f $CK/policy/bc_policy.json ]; then
  echo "$(date '+%F %T') Training Kontrolle (Seed 1, 6 Worker)"
  $P apps/train.py --dataset datasets/2026-11-09 --out $CK --steps 10000 --batch-size 128 --seed 1 \
    --num-workers 6 > $V/logs/train_kontrolle.log 2>&1 || { echo "Training Kontrolle gescheitert"; exit 1; }
fi
out=$CK/policy/rollouts/vm_T60
if [ ! -f $out/summary.json ]; then
  until vm_ok; do echo "$(date '+%F %T') warte auf VM"; sleep 120; done
  echo "$(date '+%F %T') VM-Replay Kontrolle"
  GEOFENCE=alt $P $S/stufe2_vm.py --robot neura --checkpoint $CK/policy --replay data/2026-11-11 \
    --replay-episode $T60 --out $out > $V/logs/vm_kontrolle.log 2>&1
  $P $S/eval_stufe2.py $out > /dev/null 2>&1
  $P $S/schwingen.py $out > /dev/null 2>&1
fi
echo "$(date '+%F %T') Kontrolle fertig"
