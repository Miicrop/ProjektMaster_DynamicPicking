$root='E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning'; $z='F:\Hochschule\OneDrive - Hochschule für angewandte Wissenschaften Kempten\Hochschule\Master\Robotik\Semester 3\Neuer Ordner\checkpoints'
function K($n){ $ck="$root\checkpoints\$n"; robocopy "$ck\policy" "$z\$n\policy" /E /XD rollouts /R:2 /W:5 /NP /NFL /NDL | Out-Null; Copy-Item "$ck\train_config.json","$ck\train_log.csv" "$z\$n" -Force; "$(Get-Date -f 'yyyy-MM-dd HH:mm:ss') kopiert nach $z\$n" | Add-Content -Encoding utf8 "$root\Berichte\2026-11-20_Vorlaeufig_2026-11-19\logs\kette_G2b.log" }
K 'G2c_579_nur_griff'
while (-not (Test-Path "$root\checkpoints\G2b_580_dagger_nur_griff\policy\bc_policy.json")) { Start-Sleep 30 }
Start-Sleep 20
K 'G2b_580_dagger_nur_griff'
