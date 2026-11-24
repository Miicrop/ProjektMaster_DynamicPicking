#!/usr/bin/env bash
# VM-Laeufe G2 (Kontrolle), G3 (Label gekappt), G4 (Takte ausgeblendet) auf den 39 Val-Episoden --
# NUR bei freier GPU. Befund 22.11.: VM-Lauf parallel zu einem Training -> Inferenz 150 statt 90 ms,
# ~100x mehr Takt-Ueberlaeufe, Welligkeit x3; Ergebnisse ungueltig.
# Ablauf: warten bis die Jobs 10-13 der Sim-Warteschlange fertig sind und kein apps/train.py laeuft,
# data_sim_mujoco/jobs/VM_LAEUFT anlegen (Jobs mit Sperre warten darauf), VM starten, fahren,
# VM sichern, VM_FERTIG anlegen. Aufruf aus m4_behavior_cloning.
set -u
P="E:/Enviroments/bc_env/Scripts/python.exe"
V="/c/Program Files/Oracle/VirtualBox/VBoxManage.exe"
D=Berichte/2026-11-20_Vorlaeufig_2026-11-19
J=data_sim_mujoco/jobs
log() { echo "$(date '+%F %T') $*" | tee -a $D/logs/kette_G3_G4_vm.log; }
training_laeuft() {
  powershell -NoProfile -c "if (Get-CimInstance Win32_Process | ? { \$_.Name -eq 'python.exe' -and \$_.CommandLine -match 'apps/train.py|sim_mujoco.testfahrt' }) { exit 0 } else { exit 1 }"
}
jobs_offen() {
  for f in $J/10_*.job $J/11_*.job $J/12_*.job $J/13_*.job; do
    [ -e "$f" ] || continue
    [ -e "$f.fertig" ] || [ -e "$f.fehler" ] || return 0
  done
  return 1
}
vm_ok() {
  $P -c "
import sys;sys.path.insert(0,'tools');import _bootstrap
from bc.adapters import open_robot
r=open_robot('neura');r.connect(power_on=False);ok=r.in_simulation is True;r.close();sys.exit(0 if ok else 1)" > /dev/null 2>&1
}
vm_start() {
  "$V" showvminfo Lara5_V5 --machinereadable | grep -q '^VMState="running"' || {
    log "VM starten"; "$V" startvm Lara5_V5 --type headless >> $D/logs/kette_G3_G4_vm.log 2>&1; }
  for i in $(seq 1 30); do vm_ok && { log "VM erreichbar"; return 0; }; sleep 20; done
  log "VM nach 10 min nicht erreichbar (Login noetig?)"; return 1
}

log "warte auf freie GPU (Jobs 10-13 fertig, kein Training)"
while jobs_offen || training_laeuft; do sleep 120; done
touch $J/VM_LAEUFT
log "GPU frei -> VM-Laeufe"
vm_start || { rm -f $J/VM_LAEUFT; exit 1; }
# Reset Control vorab: frischer Steuerzustand fuer alle drei Laeufe gleich
$P $D/skripte/vm_reset.py >> $D/logs/kette_G3_G4_vm.log 2>&1 || log "Reset vorab gescheitert"
for spec in G2_kontrolle=checkpoints/G2_licht_langsam_nur_griff/policy/rollouts/vm_val39_kontrolle_2026-11-23 \
            G3_kappen030=checkpoints/G3_kappen030/policy/rollouts/vm_val39 \
            G4_ausblenden030=checkpoints/G4_ausblenden030/policy/rollouts/vm_val39; do
  name=${spec%%=*}; out=${spec#*=}; ck=${out%/rollouts/*}
  [ -f $ck/bc_policy.json ] || { log "$name: keine Policy"; continue; }
  [ -f $out/auswertung.json ] && continue
  bash $D/skripte/vm_robust.sh ${name}_val39 $ck data/2026-11-19 $(cat $D/daten/val_episoden_rohdaten.txt) $out
  log "$name: VM fertig"
done
log "VM sichern"; "$V" controlvm Lara5_V5 savestate >> $D/logs/kette_G3_G4_vm.log 2>&1
rm -f $J/VM_LAEUFT; touch $J/VM_FERTIG
$P $D/skripte/tabelle_val39.py --split \
  "G2 (20.11.)=checkpoints/G2_licht_langsam_nur_griff/policy/rollouts/vm_val39" \
  "G2 Kontrolle=checkpoints/G2_licht_langsam_nur_griff/policy/rollouts/vm_val39_kontrolle_2026-11-23" \
  "G3=checkpoints/G3_kappen030/policy/rollouts/vm_val39" "G4=checkpoints/G4_ausblenden030/policy/rollouts/vm_val39" \
  > $D/daten/tabelle_G2_G3_G4.md 2>&1
log "Kette G3/G4 fertig -> $D/daten/tabelle_G2_G3_G4.md"
