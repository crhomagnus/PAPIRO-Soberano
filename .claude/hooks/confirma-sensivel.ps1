# PAPIRO hook confirma-sensivel - exige PAPIRO_CONFIRM=1 ou confirm=true (PRD §7.4 §12)
$ErrorActionPreference = 'Stop'
$raw = [Console]::In.ReadToEnd()
if ($env:PAPIRO_CONFIRM -eq '1') { exit 0 }
if ($raw -match '"confirm"\s*:\s*true') { exit 0 }
Write-Host 'BLOQUEADO confirma-sensivel: operacao papiro-seguranca exige confirmacao explicita.' -ForegroundColor Red
exit 2
