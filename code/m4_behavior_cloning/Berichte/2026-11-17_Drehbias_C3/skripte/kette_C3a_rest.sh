#!/usr/bin/env bash
# T60 C3a nachholen (VM-Abbruch 17.11. 21:12 nach 37 Fahrten), zusammenfuehren, auswerten.
set -u
P="E:/Enviroments/bc_env/Scripts/python.exe"
V=Berichte/Versuchsreihe_Policy-Varianten
S=$V/skripte
D=Berichte/2026-11-17_Drehbias_C3
R=checkpoints/C3a_wie_C2_plus_ausgeduennt/policy/rollouts
export PATH="/e/Enviroments/bc_env/Scripts:$PATH"
log() { echo "$(date '+%F %T') $*" | tee -a $D/logs/kette_C3a_rest.log; }
T60=$($P -c "import json;print(','.join(map(str,json.load(open('$V/testlagen.json'))['T60'])))")
K=$($P -c "import json;print(len(json.load(open('$R/vm_T60/summary.json'))['episodes']))")
REST=$(echo $T60 | cut -d, -f$((K + 1))-)
log "VM T60 C3a Rest ab Fahrt $K: $REST"
GEOFENCE=alt $P $S/stufe2_vm.py --robot neura --checkpoint checkpoints/C3a_wie_C2_plus_ausgeduennt/policy \
  --replay data/2026-11-11 --transport-geplant --replay-episode $REST --out $R/vm_T60_rest \
  > $D/logs/vm_T60_C3a_rest.log 2>&1 || log "Rest mit Fehler beendet"
[ -f $R/vm_T60_rest/summary.json ] || { log "Rest gescheitert"; exit 1; }
$P $S/rollouts_zusammen.py $R/vm_T60 $R/vm_T60_rest >> $D/logs/kette_C3a_rest.log 2>&1
$P $S/eval_stufe2.py $R/vm_T60 > /dev/null 2>&1
$P $D/skripte/auswertung.py > $D/logs/auswertung.log 2>&1
log "fertig"
