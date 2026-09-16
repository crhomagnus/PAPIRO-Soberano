# PAPIRO hook soberania - bloqueia rede em job sensivel (PRD §7.4 §12.5)
$ErrorActionPreference = 'Stop'
$raw = [Console]::In.ReadToEnd()
$sensivel = $false
if (Test-Path 'C:\PAPIRO\work\_sensivel.flag') { $sensivel = $true }
if ($raw -match 'sensivel.{0,5}true') { $sensivel = $true }
if ($sensivel -and ($raw -match 'webfetch|websearch|Invoke-WebRequest|curl.*http|http')) {
  Write-Host 'BLOQUEADO soberania: job sensivel sem rede.' -ForegroundColor Red
  exit 2
}
exit 0
