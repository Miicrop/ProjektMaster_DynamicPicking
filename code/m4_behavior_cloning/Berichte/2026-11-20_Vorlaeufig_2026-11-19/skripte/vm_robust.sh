#!/usr/bin/env bash
# VM-Replay, das einen VM-Haenger ("arm steht", servo_j wird nicht mehr angenommen) selbst behebt:
# Lauf bis zur ersten Fahrt mit "arm steht" behalten, Reset Control (skripte/vm_reset.py),
# Rest der Episodenliste nachfahren und anhaengen (rollouts_zusammen.py). Hoechstens 4 Runden.
# Aufruf (aus m4_behavior_cloning): vm_robust.sh <name> <policy> <aufnahme> <episodenliste> <out>
set -u
P="E:/Enviroments/bc_env/Scripts/python.exe"
D=Berichte/2026-11-20_Vorlaeufig_2026-11-19
S=Berichte/Versuchsreihe_Policy-Varianten/skripte
name=$1 ck=$2 data=$3 eps=$4 out=$5
log() { echo "$(date '+%F %T') $*" | tee -a $D/logs/vm_robust_$name.log; }

run_part() {  # liste ordner logdatei
  GEOFENCE=alt $P $S/stufe2_vm.py --robot neura --checkpoint $ck --replay $data \
    --replay-episode $1 --transport-geplant --out $2 > $3 2>&1 || log "Lauf $2 mit Fehler beendet"
}
# erste Fahrt mit "arm steht" (Nummer im Lauf) oder leer
first_stuck() {
  grep -E "^Fahrt [0-9]+: kein Erfolg .*arm steht" $1 | head -1 | sed -E 's/^Fahrt ([0-9]+):.*/\1/'
}
# Lauf auf Fahrten 0..k-1 kuerzen
truncate_run() {
  $P - "$1" "$2" <<'EOF'
import json, sys
from pathlib import Path
run, k = Path(sys.argv[1]), int(sys.argv[2])
s = json.loads((run / "summary.json").read_text(encoding="utf-8"))
s["episodes"] = [e for e in s["episodes"] if e["episode"] < k]
(run / "summary.json").write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding="utf-8")
for f in run.glob("rollout_*.npz"):
    if int(f.stem.split("_")[1]) >= k:
        f.unlink()
print("gekuerzt auf %d Fahrten" % k)
EOF
}

rm -rf $out
log "$name: Lauf 1 ($eps)"
run_part $eps $out $D/logs/vm_${name}.log
[ -f $out/summary.json ] || { log "$name: Lauf 1 ohne summary.json"; exit 1; }
# k = Nummer der ersten haengenden Fahrt im zuletzt gefahrenen Teil (relativ zu rest_list)
k=$(first_stuck $D/logs/vm_${name}.log)
[ -n "$k" ] && truncate_run $out $k > /dev/null
rest_list=$eps
for runde in 2 3 4; do
  [ -z "$k" ] && break
  rest_list=$(echo $rest_list | cut -d, -f$((k + 1))-)
  log "$name: arm steht ab Fahrt $k des letzten Teils -> Reset Control, Rest: $rest_list"
  $P $D/skripte/vm_reset.py >> $D/logs/vm_robust_$name.log 2>&1 || { log "Reset gescheitert"; break; }
  rm -rf ${out}_rest
  run_part $rest_list ${out}_rest $D/logs/vm_${name}_rest$runde.log
  [ -f ${out}_rest/summary.json ] || { log "Rest-Lauf ohne summary.json"; break; }
  k=$(first_stuck $D/logs/vm_${name}_rest$runde.log)
  [ -n "$k" ] && truncate_run ${out}_rest $k > /dev/null
  $P $S/rollouts_zusammen.py $out ${out}_rest >> $D/logs/vm_robust_$name.log 2>&1
  rm -rf ${out}_rest
done
[ -n "$k" ] && log "$name: nach 4 Runden haengt die VM weiter -- Lauf unvollstaendig"
$P $S/eval_stufe2.py $out > /dev/null 2>&1
$P $S/schwingen.py $out > /dev/null 2>&1
n=$($P -c "import json;print(len(json.load(open('$out/summary.json'))['episodes']))")
log "$name fertig: $n Fahrten in $out"
