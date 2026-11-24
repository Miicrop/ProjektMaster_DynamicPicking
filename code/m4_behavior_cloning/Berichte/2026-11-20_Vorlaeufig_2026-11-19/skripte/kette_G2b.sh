#!/usr/bin/env bash
# 1) G2c: G2-Rezept (0,02 m/s, nur bis Griff, 10 000 Schritte) mit 19.11. + 23.11., OHNE DAgger.
# 2) G2b: dasselbe + DAgger 23.11. (0-3 = Testfahrten vormittags, weggelassen).
# Aufruf aus m4_behavior_cloning.
set -u
P="E:/Enviroments/bc_env/Scripts/python.exe"; D=Berichte/2026-11-20_Vorlaeufig_2026-11-19
log() { echo "$(date '+%F %T') $*" | tee -a $D/logs/kette_G2b.log; }
lauf() {  # name dataset checkpoint datenquellen...
  name=$1 DS=$2 CK=$3; shift 3
  if [ ! -f $DS/meta/bc_export.json ]; then
    log "Export $name"
    $P tools/export_variante.py --data "$@" --abschneiden-nach 3 --overwrite --out $DS \
      > $D/logs/export_$name.log 2>&1 || { log "Export $name gescheitert"; return 1; }
  fi
  if [ ! -f $CK/policy/bc_policy.json ]; then
    log "Training $name"
    $P -u apps/train.py --dataset $DS --out $CK --steps 10000 --batch-size 128 --num-workers 6 \
      > $D/logs/train_$name.log 2>&1 || { log "Training $name gescheitert"; return 1; }
  fi
  log "$name fertig"
}
lauf G2c datasets/2026-11-19_23_nur_griff checkpoints/G2c_579_nur_griff data/2026-11-19 data/2026-11-23
lauf G2b datasets/2026-11-19_23_dagger_nur_griff checkpoints/G2b_580_dagger_nur_griff \
  data/2026-11-19 data/2026-11-23 data/2026-11-23_dagger --ohne-episoden data/2026-11-23_dagger=0,1,2,3
