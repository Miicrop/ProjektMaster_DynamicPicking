# Wartet auf G2c, stoppt die Kette vor G2b, kopiert den Checkpoint (USB-Stick falls vorhanden + OneDrive), faehrt herunter.
$ErrorActionPreference = 'Continue'
$root = 'E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning'
$ck = "$root\checkpoints\G2c_579_nur_griff"
$log = "$root\Berichte\2026-11-20_Vorlaeufig_2026-11-19\logs\kette_G2b.log"
function L($m) { "$(Get-Date -f 'yyyy-MM-dd HH:mm:ss') $m" | Add-Content -Encoding utf8 $log }
while (-not (Test-Path "$ck\policy\bc_policy.json")) { Start-Sleep 30 }
Start-Sleep 20
# Kette stoppen (bash + ggf. gestarteter G2b-Export/Training)
Get-CimInstance Win32_Process | ? { $_.CommandLine -match 'kette_G2b.sh|export_variante|G2b_580' -and $_.CommandLine -notmatch 'Get-CimInstance|g2c_abschluss' } | % { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
L "G2c fertig -> Kette vor G2b gestoppt (G2b morgen)"
$ziele = @('F:\Personal\OneDrive\Projekt\80_Github\ProjektMaster_DynamicPicking\code\m4_behavior_cloning\checkpoints')
Get-CimInstance Win32_LogicalDisk | ? { $_.DriveType -eq 2 } | % { $ziele += "$($_.DeviceID)\checkpoints" }
foreach ($z in $ziele) {
  $dst = "$z\G2c_579_nur_griff"
  robocopy "$ck\policy" "$dst\policy" /E /XD rollouts /R:2 /W:5 /NP /NFL /NDL | Out-Null
  Copy-Item "$ck\train_config.json", "$ck\train_log.csv" $dst -Force
  L "kopiert nach $dst ($([math]::Round(((Get-ChildItem $dst -Recurse | Measure-Object Length -Sum).Sum/1MB),0)) MB)"
}
L "warte 20 min auf OneDrive-Upload, dann Herunterfahren"
Start-Sleep 1200
L "Herunterfahren"
shutdown /s /t 60 /c "G2c fertig - Herunterfahren"
