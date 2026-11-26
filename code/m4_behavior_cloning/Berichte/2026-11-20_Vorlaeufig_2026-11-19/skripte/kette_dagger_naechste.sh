#!/usr/bin/env bash
# Vorlage fuer die naechste DAgger-Runde (z. B. auf dem Anlagen-Laptop):
#   bash kette_dagger_naechste.sh <name> <startmodell-ordner> <datensatz> <checkpoint> <datenquellen...>
# Beispiel:
#   bash $D/kette_dagger_naechste.sh G2b-D2 checkpoints/G2b-D_669_dagger2511_val_fest \
#     datasets/G2b-D2 checkpoints/G2b-D2_val_fest data/2026-11-19 data/2026-11-23 \
#     data/2026-11-23_dagger data/G2c data/2026-11-XX_dagger --ohne-episoden data/2026-11-23_dagger=0,1,2,3
# Startmodelle ab 26.11. tragen val_keys in train_config.json -> alter Datensatz nicht noetig.
# Aeltere (G2, G2b) brauchen ihren damaligen Datensatz unter dem Pfad aus train_config.json.
set -u
P="${P:-E:/Enviroments/bc_env/Scripts/python.exe}"; STEPS="${STEPS:-3000}"
name=$1 START=$2 DS=$3 CK=$4; shift 4
mkdir -p logs
[ -f $DS/meta/bc_export.json ] || $P tools/export_variante.py --data "$@" --abschneiden-nach 3 \
  --overwrite --out $DS > logs/export_$name.log 2>&1 || { echo "Export gescheitert"; exit 1; }
$P -u apps/train.py --dataset $DS --out $CK --init-from $START/policy --val-wie $START \
  --steps $STEPS --batch-size 128 --num-workers 6 > logs/train_$name.log 2>&1 \
  || { echo "Training gescheitert"; exit 1; }
grep -E "val-wie|Datensatz " logs/train_$name.log
