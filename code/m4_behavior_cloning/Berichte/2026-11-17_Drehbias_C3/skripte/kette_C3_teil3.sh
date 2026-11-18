#!/usr/bin/env bash
# Fruehentscheidung auf den zurueckgehaltenen Demos vom 11.11. fuer C3 und C3a,
# je sobald das Training fertig ist. Aufruf aus m4_behavior_cloning.
set -u
export PATH="/e/Enviroments/bc_env/Scripts:$PATH"
P="E:/Enviroments/bc_env/Scripts/python.exe"
D=Berichte/2026-11-17_Drehbias_C3
for m in C3 C3a; do
  until [ -f checkpoints/var_$m/policy/bc_policy.json ]; do sleep 60; done
  sleep 30
  if [ ! -f $D/daten/frueh_1111_$m.json ]; then
    echo "$(date '+%F %T') Fruehentscheidung 11.11. $m"
    $P -u $D/skripte/nachstellen_offline.py --daten data/2026-11-11 --nur-frueh --samples 4 \
      --modelle $m=checkpoints/var_$m/policy --out $D/daten/frueh_1111_$m.json > $D/logs/frueh_1111_$m.log 2>&1
  fi
done
echo "$(date '+%F %T') Teil 3 fertig"
