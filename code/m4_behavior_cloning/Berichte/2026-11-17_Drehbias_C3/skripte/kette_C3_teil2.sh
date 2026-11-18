#!/usr/bin/env bash
# Teil 2 nach dem Training (kette_C3.sh): Offline-Nachbau der Anlagenfahrten 17.11.,
# dann VM-Replay (wartet auf die VM): heutige Fahrten (DAgger-Bilder) und T60.
# Aufruf aus m4_behavior_cloning.
set -u
export PATH="/e/Enviroments/bc_env/Scripts:$PATH"
P="E:/Enviroments/bc_env/Scripts/python.exe"
D=Berichte/2026-11-17_Drehbias_C3
S=Berichte/Versuchsreihe_Policy-Varianten/skripte
T60=$($P -c "import json;print(','.join(map(str,json.load(open('Berichte/Versuchsreihe_Policy-Varianten/testlagen.json'))['T60'])))")
log() { echo "$(date '+%F %T') $*"; }

until [ -f checkpoints/C3a_wie_C2_plus_ausgeduennt/policy/bc_policy.json ]; do sleep 60; done
while pgrep -f "apps/train.py" > /dev/null 2>&1 || tasklist | grep -qi "train.py"; do sleep 30; done
log "Trainings fertig"

if [ ! -f $D/daten/offline.json ]; then
  log "Offline-Nachbau C2/C3/C3a"
  $P $D/skripte/nachstellen_offline.py --samples 8 --out $D/daten/offline.json \
    --modelle C2=checkpoints/C2_nur_griff_ohne_1111/policy C3=checkpoints/C3_wie_C2_drehung_gewichtet/policy C3a=checkpoints/C3a_wie_C2_plus_ausgeduennt/policy \
    > $D/logs/offline.log 2>&1 || log "Offline gescheitert"
fi

vm_ok() {
  $P -c "
import os,sys;sys.path.insert(0,'tools');import _bootstrap
from bc.adapters import open_robot
r=open_robot('neura');r.connect(power_on=False);ok=r.in_simulation is True;r.close();sys.exit(0 if ok else 1)" > /dev/null 2>&1
}
n=0
until vm_ok; do
  [ $((n % 15)) -eq 0 ] && log "warte auf VM (VirtualBox Lara5_V5 starten, in der Bedienoberflaeche Automatikmodus)"
  n=$((n+1)); sleep 120
done
log "VM erreichbar (in_simulation = True)"

vm_run() {  # name checkpoint replay episoden out extra
  local name=$1 ck=$2 data=$3 eps=$4 out=$5
  if [ -f $out/summary.json ]; then return; fi
  until vm_ok; do log "warte auf VM ($name)"; sleep 120; done
  log "VM $name -> $out"
  GEOFENCE=alt $P $S/stufe2_vm.py --robot neura --checkpoint $ck --replay $data \
    --replay-episode $eps --transport-geplant --out $out > $D/logs/vm_$name.log 2>&1 \
    || log "VM $name mit Fehler beendet (siehe logs/vm_$name.log)"
}
# 1. heutige Anlagenfahrten (Bilder der var_C2-Fahrten), C2 zweimal (Streuung der VM)
vm_run heute_C2   checkpoints/C2_nur_griff_ohne_1111/policy  data/2026-11-17_dagger alle checkpoints/C2_nur_griff_ohne_1111/policy/rollouts/vm_heute_2026-11-17
vm_run heute_C3   checkpoints/C3_wie_C2_drehung_gewichtet/policy  data/2026-11-17_dagger alle checkpoints/C3_wie_C2_drehung_gewichtet/policy/rollouts/vm_heute_2026-11-17
vm_run heute_C3a  checkpoints/C3a_wie_C2_plus_ausgeduennt/policy data/2026-11-17_dagger alle checkpoints/C3a_wie_C2_plus_ausgeduennt/policy/rollouts/vm_heute_2026-11-17
vm_run heute_C2w  checkpoints/C2_nur_griff_ohne_1111/policy  data/2026-11-17_dagger alle checkpoints/C2_nur_griff_ohne_1111/policy/rollouts/vm_heute_2026-11-17_wdh
# 2. Testlagen T60 (Bilder der Demos vom 11.11., wie Versuchsreihe)
vm_run T60_C3     checkpoints/C3_wie_C2_drehung_gewichtet/policy  data/2026-11-11 $T60 checkpoints/C3_wie_C2_drehung_gewichtet/policy/rollouts/vm_T60
vm_run T60_C3a    checkpoints/C3a_wie_C2_plus_ausgeduennt/policy data/2026-11-11 $T60 checkpoints/C3a_wie_C2_plus_ausgeduennt/policy/rollouts/vm_T60
for m in C3 C3a; do
  $P $S/eval_stufe2.py checkpoints/var_$m/policy/rollouts/vm_T60 > /dev/null 2>&1
done
log "Kette C3 Teil 2 fertig"
