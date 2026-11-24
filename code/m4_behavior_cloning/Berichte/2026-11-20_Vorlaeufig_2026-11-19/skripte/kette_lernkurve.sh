#!/usr/bin/env bash
# Lernkurve auf den G2-Daten: 50 % und 75 % der Trainings-Lagen (lernkurve/gewichte_*.json),
# sonst alles wie G2 (Datensatz, Split, Seed 0, 10 000 Schritte, Batch 128).
# Danach VM-Replay auf denselben 39 Val-Episoden (vm_robust.sh, mit Reset Control bei Haengern).
# Aufruf aus m4_behavior_cloning.
set -u
P="E:/Enviroments/bc_env/Scripts/python.exe"
D=Berichte/2026-11-20_Vorlaeufig_2026-11-19
log() { echo "$(date '+%F %T') $*"; }
for pct in 50 75; do
  CK=checkpoints/G2_lernkurve_${pct}
  if [ ! -f $CK/policy/bc_policy.json ]; then
    log "Training ${pct} %"
    $P -u apps/train.py --dataset datasets/2026-11-19_nur_griff --out $CK --steps 10000 --batch-size 128 \
      --num-workers 6 --episoden-gewichte $D/lernkurve/gewichte_${pct}.json > $D/logs/train_L${pct}.log 2>&1 \
      || { log "Training ${pct} % gescheitert"; continue; }
    log "Training ${pct} % fertig: $(grep '^step  10000' $D/logs/train_L${pct}.log | sed 's/.*| //')"
  fi
done
for pct in 50 75; do
  CK=checkpoints/G2_lernkurve_${pct}
  [ -f $CK/policy/bc_policy.json ] || continue
  [ -f $CK/policy/rollouts/vm_val39/auswertung.json ] && continue
  until $P -c "
import sys;sys.path.insert(0,'tools');import _bootstrap
from bc.adapters import open_robot
r=open_robot('neura');r.connect(power_on=False);ok=r.in_simulation is True;r.close();sys.exit(0 if ok else 1)" > /dev/null 2>&1
  do log "warte auf VM (${pct} %)"; sleep 120; done
  log "VM ${pct} % start"
  bash $D/skripte/vm_robust.sh L${pct}_val39 $CK/policy data/2026-11-19 $(cat $D/daten/val_episoden_rohdaten.txt) \
    $CK/policy/rollouts/vm_val39
  log "VM ${pct} % fertig"
done
log "Kette Lernkurve fertig"
