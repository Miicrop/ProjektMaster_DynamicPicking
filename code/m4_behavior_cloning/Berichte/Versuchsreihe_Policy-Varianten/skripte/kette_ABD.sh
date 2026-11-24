#!/usr/bin/env bash
# Export und Training der Varianten A, B, D nacheinander (Versuchsreihe Policy-Varianten).
# Wartet, bis der Inferenz-Vergleich (I) fertig ist, damit Videokodierung/Training die
# Taktzeiten der VM-Fahrten nicht verfaelschen.
# Aufruf aus m4_behavior_cloning:  bash Berichte/Versuchsreihe_Policy-Varianten/skripte/kette_ABD.sh
set -u
P="E:/Enviroments/bc_env/Scripts/python.exe"
V=Berichte/Versuchsreihe_Policy-Varianten
T=$V/testlagen.json
D="data/2026-11-02 data/2026-11-03 data/2026-11-09 data/2026-11-11"
mkdir -p $V/logs

if [ "${OHNE_WARTEN:-0}" != 1 ]; then
  until grep -q "^Erfolg" $V/logs/inferenz_ohne-mitteln.log 2>/dev/null; do sleep 30; done
  echo "$(date '+%F %T') Inferenz-Vergleich fertig"
fi
echo "$(date '+%F %T') starte Exporte"

declare -A REGEL=( [A]="" [B]="--pause-behalten 3" [D]="--eine-drehung" )
for v in A B D; do
  if [ ! -f datasets/var_$v/meta/bc_export.json ]; then
    echo "$(date '+%F %T') Export $v"
    $P tools/export_variante.py --data $D --ohne-lagen $T ${REGEL[$v]} --out datasets/var_$v \
      > $V/logs/export_$v.log 2>&1 || { echo "Export $v gescheitert"; exit 1; }
  fi
done
for v in A B D; do
  if [ ! -f checkpoints/var_$v/policy/bc_policy.json ]; then
    echo "$(date '+%F %T') Training $v"
    $P apps/train.py --dataset datasets/var_$v --out checkpoints/var_$v --steps 10000 --batch-size 128 \
      > $V/logs/train_$v.log 2>&1 || { echo "Training $v gescheitert"; exit 1; }
  fi
done
echo "$(date '+%F %T') Kette fertig"
