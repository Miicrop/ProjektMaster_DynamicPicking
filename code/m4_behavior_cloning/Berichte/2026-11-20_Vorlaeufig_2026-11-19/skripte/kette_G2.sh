#!/usr/bin/env bash
# G2 = G, aber Episoden 3 Takte nach dem Schliessen beendet (wie C2).
# Export -> Training (10 000 Schritte, Batch 128, Seed 0) -> Offline-Test 19-2
# -> VM-Replay auf denselben 39 Val-Episoden wie G (wartet auf die VM).
# Aufruf aus m4_behavior_cloning.
set -u
P="E:/Enviroments/bc_env/Scripts/python.exe"
D=Berichte/2026-11-20_Vorlaeufig_2026-11-19
S=Berichte/Versuchsreihe_Policy-Varianten/skripte
DS=datasets/2026-11-19_nur_griff
CK=checkpoints/G2_licht_langsam_nur_griff
log() { echo "$(date '+%F %T') $*"; }
vm_ok() {
  $P -c "
import os,sys;sys.path.insert(0,'tools');import _bootstrap
from bc.adapters import open_robot
r=open_robot('neura');r.connect(power_on=False);ok=r.in_simulation is True;r.close();sys.exit(0 if ok else 1)" > /dev/null 2>&1
}

if [ ! -f $DS/meta/bc_export.json ]; then
  log "Export G2"
  $P tools/export_variante.py --data data/2026-11-19 --abschneiden-nach 3 --overwrite --out $DS \
    > $D/logs/export_G2.log 2>&1 || { log "Export G2 gescheitert"; exit 1; }
  log "Export G2 fertig"
fi
if [ ! -f $CK/policy/bc_policy.json ]; then
  log "Training G2"
  $P -u apps/train.py --dataset $DS --out $CK --steps 10000 --batch-size 128 --num-workers 6 \
    > $D/logs/train_G2.log 2>&1 || { log "Training G2 gescheitert"; exit 1; }
  log "Training G2 fertig: $(grep '^step  10000' $D/logs/train_G2.log | sed 's/.*| //')"
fi
$P - <<EOF && log "Val-Split gleich wie G" || log "ACHTUNG: Val-Split anders als bei G"
import json, sys
a = json.load(open("checkpoints/G_licht_langsam_2026-11-19/train_config.json"))["val_episodes"]
b = json.load(open("$CK/train_config.json"))["val_episodes"]
sys.exit(0 if a == b else 1)
EOF
if [ ! -f $D/daten/test_offline_G2.json ]; then
  log "Offline-Test G2"
  $P -u $D/skripte/test_offline.py --daten data/2026-11-19-2 --modelle G2=$CK/policy \
    --out $D/daten/test_offline_G2.json > $D/logs/test_offline_G2.log 2>&1 \
    && log "Offline-Test G2 fertig: $(grep GESAMT $D/logs/test_offline_G2.log | cut -c1-400)" \
    || log "Offline-Test G2 gescheitert"
fi
out=$CK/policy/rollouts/vm_val39
if [ ! -f $out/summary.json ]; then
  until vm_ok; do log "warte auf VM"; sleep 60; done
  log "VM G2 val39 start"
  GEOFENCE=alt $P $S/stufe2_vm.py --robot neura --checkpoint $CK/policy --replay data/2026-11-19 \
    --replay-episode $(cat $D/daten/val_episoden_rohdaten.txt) --transport-geplant --out $out \
    > $D/logs/vm_G2_val39.log 2>&1 || log "VM G2 mit Fehler beendet"
  $P $S/eval_stufe2.py $out > /dev/null 2>&1
  $P $S/schwingen.py $out > /dev/null 2>&1
  log "VM G2 val39 fertig: $(grep '^Erfolg' $D/logs/vm_G2_val39.log)"
fi
log "Kette G2 fertig"
