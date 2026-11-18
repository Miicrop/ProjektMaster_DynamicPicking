#!/usr/bin/env bash
# Ersetzt kette_F.sh nach dem VM-Ausfall am 14.11. 13:41 (C2-VM-Lauf nach 29 von 59 Fahrten
# abgebrochen, CORBA COMM_FAILURE). Reihenfolge, damit VM-Fahrten nie neben einem Training laufen:
#   1. Training F (A + --licht-augment), braucht die VM nicht
#   2. C2: restliche Fahrten (T60 ab Fahrt 29) nachholen und mit Teil 1 zusammenfuehren
#   3. VM-Replay F
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
warte_vm() { until vm_ok; do echo "$(date '+%F %T') warte auf VM"; sleep 120; done; }

# 1. Training F
CK=checkpoints/F_licht_augment
if [ ! -f $CK/policy/bc_policy.json ]; then
  echo "$(date '+%F %T') Training F (A + Licht-Augmentierung)"
  $P apps/train.py --dataset datasets/var_A --out $CK --steps 10000 --batch-size 128 --licht-augment \
    --num-workers 6 > $V/logs/train_F.log 2>&1 || { echo "Training F gescheitert"; exit 1; }
fi

# 2. C2 Rest
C2=checkpoints/C2_nur_griff_ohne_1111/policy/rollouts
if ! grep -q zusammengefuehrt $C2/vm_T60/summary.json 2>/dev/null; then
  if [ ! -f $C2/vm_T60/summary.json ]; then
    $P $S/summary_aus_log.py $C2/vm_T60 $V/logs/vm_C2.log data/2026-11-11 $T60
  fi
  K=$($P -c "import json;print(len(json.load(open('$C2/vm_T60/summary.json'))['episodes']))")
  REST=$(echo $T60 | cut -d, -f$((K + 1))-)
  if [ ! -f $C2/vm_T60_rest/summary.json ]; then
    warte_vm
    echo "$(date '+%F %T') VM-Replay C2 Rest (ab Fahrt $K)"
    GEOFENCE=alt $P $S/stufe2_vm.py --robot neura --checkpoint checkpoints/C2_nur_griff_ohne_1111/policy --replay data/2026-11-11 \
      --transport-geplant --replay-episode $REST --out $C2/vm_T60_rest > $V/logs/vm_C2_rest.log 2>&1
  fi
  [ -f $C2/vm_T60_rest/summary.json ] || { echo "C2 Rest gescheitert"; exit 1; }
  $P $S/rollouts_zusammen.py $C2/vm_T60 $C2/vm_T60_rest
  $P $S/eval_stufe2.py $C2/vm_T60 > /dev/null 2>&1
  $P $S/schwingen.py $C2/vm_T60 > /dev/null 2>&1
  echo "$(date '+%F %T') C2 vollstaendig"
fi

# 3. VM F
out=$CK/policy/rollouts/vm_T60
if [ ! -f $out/summary.json ]; then
  warte_vm
  echo "$(date '+%F %T') VM-Replay F"
  GEOFENCE=alt $P $S/stufe2_vm.py --robot neura --checkpoint $CK/policy --replay data/2026-11-11 \
    --replay-episode $T60 --out $out > $V/logs/vm_F.log 2>&1
  $P $S/eval_stufe2.py $out > /dev/null 2>&1
  $P $S/schwingen.py $out > /dev/null 2>&1
fi
echo "$(date '+%F %T') Kette F fertig"
