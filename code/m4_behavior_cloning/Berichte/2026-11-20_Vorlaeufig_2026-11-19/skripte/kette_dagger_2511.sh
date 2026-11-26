#!/usr/bin/env bash
# Nachbau (Original auf dem RTX-5070-Ti-PC nicht committet).
# DAgger 25.11.: G2 und G2b mit --init-from nachtrainieren, 3000 Schritte, nur bis 3 Takte nach Griff.
#   G2-D : 19.11. + data/G2  (50 Fahrten mit G2, inkl. ep_00054)            = 449 Episoden
#   G2b-D: 19.11. + 23.11. + 23.11._dagger (ohne 0-3) + data/G2c (50 mit G2b) = 669 Episoden
# Aufteilung: --val-wie Startmodell (alte Val bleiben Val, nur neue Fahrten 10 % Seed 0).
# Aufruf aus m4_behavior_cloning. Zweites Argument von lauf = Startmodell.
set -u
P="E:/Enviroments/bc_env/Scripts/python.exe"; D=Berichte/2026-11-20_Vorlaeufig_2026-11-19
mkdir -p $D/logs
log() { echo "$(date '+%F %T') $*" | tee -a $D/logs/kette_dagger_2511.log; }
lauf() {  # name startmodell dataset checkpoint datenquellen...
  name=$1 START=$2 DS=$3 CK=$4; shift 4
  if [ ! -f $DS/meta/bc_export.json ]; then
    log "Export $name"
    $P tools/export_variante.py --data "$@" --abschneiden-nach 3 --overwrite --out $DS \
      > $D/logs/export_$name.log 2>&1 || { log "Export $name gescheitert"; return 1; }
  fi
  if [ ! -f $CK/policy/bc_policy.json ]; then
    log "Training $name"
    $P -u apps/train.py --dataset $DS --out $CK --init-from $START/policy --val-wie $START \
      --steps 3000 --batch-size 128 --num-workers 6 \
      > $D/logs/train_$name.log 2>&1 || { log "Training $name gescheitert"; return 1; }
  fi
  log "$name fertig: $(grep -E 'val-wie|Datensatz ' $D/logs/train_$name.log | tr '\n' ' ')"
}
lauf G2-D checkpoints/G2_licht_langsam_nur_griff datasets/G2-D_449_dagger2511 \
  checkpoints/G2-D_449_dagger2511_val_fest data/2026-11-19 data/G2
lauf G2b-D checkpoints/G2b_580_dagger_nur_griff datasets/G2b-D_669_dagger2511 \
  checkpoints/G2b-D_669_dagger2511_val_fest \
  data/2026-11-19 data/2026-11-23 data/2026-11-23_dagger data/G2c --ohne-episoden data/2026-11-23_dagger=0,1,2,3
log "Kette dagger_2511 fertig"
