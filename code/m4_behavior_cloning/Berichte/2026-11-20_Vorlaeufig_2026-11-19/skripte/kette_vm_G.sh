#!/usr/bin/env bash
# VM-Replay fuer Modell G (Daten 19.11.), wartet auf die VM.
#  1. G  auf data/2026-11-19-2 (7 Episoden, neue Bilder)
#  2. C2 auf data/2026-11-19-2 (Gegenprobe, fuer C2 fremde Bilder)
#  3. G  auf T60 (data/2026-11-11, alte Bilder; C2 hat dort vm_T60)
# Bedingungen wie C2/C3: GEOFENCE=alt, --transport-geplant.
# Aufruf aus m4_behavior_cloning.
set -u
P="E:/Enviroments/bc_env/Scripts/python.exe"
D=Berichte/2026-11-20_Vorlaeufig_2026-11-19
S=Berichte/Versuchsreihe_Policy-Varianten/skripte
T60=$($P -c "import json;print(','.join(map(str,json.load(open('Berichte/Versuchsreihe_Policy-Varianten/testlagen.json'))['T60'])))")
G=checkpoints/G_licht_langsam_2026-11-19/policy
C2=checkpoints/C2_nur_griff_ohne_1111/policy
log() { echo "$(date '+%F %T') $*"; }
vm_ok() {
  $P -c "
import os,sys;sys.path.insert(0,'tools');import _bootstrap
from bc.adapters import open_robot
r=open_robot('neura');r.connect(power_on=False);ok=r.in_simulation is True;r.close();sys.exit(0 if ok else 1)" > /dev/null 2>&1
}
vm_run() {  # name checkpoint replay episoden out
  local name=$1 ck=$2 data=$3 eps=$4 out=$5
  [ -f $out/summary.json ] && { log "$name schon vorhanden"; return; }
  until vm_ok; do log "warte auf VM ($name)"; sleep 60; done
  log "VM $name start"
  GEOFENCE=alt $P $S/stufe2_vm.py --robot neura --checkpoint $ck --replay $data \
    --replay-episode $eps --transport-geplant --out $out > $D/logs/vm_$name.log 2>&1 \
    || log "VM $name mit Fehler beendet (siehe logs/vm_$name.log)"
  if [ -f $out/summary.json ]; then
    $P $S/eval_stufe2.py $out > /dev/null 2>&1
    $P $S/schwingen.py $out > /dev/null 2>&1
    log "VM $name fertig"
  else
    log "VM $name ohne summary.json"
  fi
}
vm_run G_19-2  $G  data/2026-11-19-2 alle $G/rollouts/vm_2026-11-19-2
vm_run C2_19-2 $C2 data/2026-11-19-2 alle $C2/rollouts/vm_2026-11-19-2
vm_run G_T60   $G  data/2026-11-11   $T60 $G/rollouts/vm_T60
log "Kette fertig"
