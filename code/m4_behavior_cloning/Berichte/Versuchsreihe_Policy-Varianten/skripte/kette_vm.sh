#!/usr/bin/env bash
# VM-Replay der Varianten A-D auf den Testlagen T60, danach Auswertung und Vergleich.
# Wartet, bis alle Trainings fertig sind (GPU frei) und die VM antwortet.
# GEOFENCE=alt: Kollisionsmodell wie Checkpoint 2026-11-09 (gleiche Bedingungen);
# Tisch-/Huellenverstoesse werden aus den Protokollen nachgerechnet.
# Aufruf aus m4_behavior_cloning.
set -u
P="E:/Enviroments/bc_env/Scripts/python.exe"
V=Berichte/Versuchsreihe_Policy-Varianten
S=$V/skripte
T60=$($P -c "import json;print(','.join(map(str,json.load(open('$V/testlagen.json'))['T60'])))")
vm_ok() {
  $P -c "
import os,sys;sys.path.insert(0,'tools');import _bootstrap
from bc.adapters import open_robot
r=open_robot('neura');r.connect(power_on=False);ok=r.in_simulation is True;r.close();sys.exit(0 if ok else 1)" > /dev/null 2>&1
}

until grep -q "Kette C fertig" $V/logs/kette_C.log 2>/dev/null; do sleep 60; done
for v in A B C D; do
  out=checkpoints/var_$v/policy/rollouts/vm_T60
  [ -f $out/summary.json ] && continue
  until vm_ok; do echo "$(date '+%F %T') warte auf VM"; sleep 120; done
  extra=""; [ $v = C ] && extra="--transport-geplant"
  echo "$(date '+%F %T') VM-Replay $v"
  GEOFENCE=alt $P $S/stufe2_vm.py --robot neura --checkpoint checkpoints/var_$v/policy --replay data/2026-11-11 \
    --replay-episode $T60 $extra --out $out > $V/logs/vm_$v.log 2>&1
  if [ ! -f $out/summary.json ]; then echo "$(date '+%F %T') VM-Replay $v abgebrochen (siehe logs/vm_$v.log)"; continue; fi
  $P $S/eval_stufe2.py $out > /dev/null 2>&1
  $P $S/schwingen.py $out > /dev/null 2>&1
done
R=checkpoints/2026-11-09/policy/rollouts/2026-11-13_vm_replay_daten-2026-11-11
PYTHONIOENCODING=utf-8 $P $S/vergleich.py "Checkpoint 2026-11-09=$R" \
  "A Basis=checkpoints/var_A/policy/rollouts/vm_T60" "B Pause kurz=checkpoints/var_B/policy/rollouts/vm_T60" \
  "C Nur Griff=checkpoints/var_C/policy/rollouts/vm_T60" "D Eine Drehung=checkpoints/var_D/policy/rollouts/vm_T60" \
  > $V/vergleich_T60.md 2> $V/logs/vergleich.log
echo "$(date '+%F %T') VM-Kette fertig"
