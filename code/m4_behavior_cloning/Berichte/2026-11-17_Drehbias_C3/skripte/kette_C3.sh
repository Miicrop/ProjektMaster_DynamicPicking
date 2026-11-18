#!/usr/bin/env bash
# C3 = var_C2 mit ausgeglichener Drehrichtung (Anlage 2026-11-17: Minus-Lagen falsch gedreht).
# Gleicher Datensatz (datasets/var_C2), gleicher Split, Seed 0, 10 000 Schritte, Batch 128 --
# einzige Aenderung: Ziehgewicht je Episode (tools/drehung_ausgleich.py).
#   var_C3  : MINUS-Episoden x 2,83 (gleiche Frame-Masse plus/minus)
#   var_C3a : 238 von 373 PLUS-Episoden nie gezogen ("Plus-Fahrten rausnehmen")
# Aufruf aus m4_behavior_cloning.
set -u
export PATH="/e/Enviroments/bc_env/Scripts:$PATH"
P="E:/Enviroments/bc_env/Scripts/python.exe"
D=Berichte/2026-11-17_Drehbias_C3
for V in C3:gewichten C3a:ausduennen; do
  name=${V%%:*}; modus=${V##*:}
  CK=checkpoints/var_$name
  if [ ! -f $CK/policy/bc_policy.json ]; then
    echo "$(date '+%F %T') Training $name ($modus)"
    $P apps/train.py --dataset datasets/var_C2 --out $CK --steps 10000 --batch-size 128 \
      --num-workers 6 --episoden-gewichte $D/gewichte_C3_$modus.json \
      > $D/logs/train_$name.log 2>&1 || { echo "Training $name gescheitert"; exit 1; }
  fi
done
echo "$(date '+%F %T') Kette C3 fertig"
