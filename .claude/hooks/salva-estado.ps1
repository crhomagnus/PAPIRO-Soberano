# PAPIRO hook salva-estado - persiste plano+status dos jobs antes do compact (nao bloqueia)
$ErrorActionPreference = 'SilentlyContinue'
$db = 'C:\PAPIRO\logs\jobs.db'
if (Test-Path $db) {
  Copy-Item $db "C:\PAPIRO\logs\jobs.precompact.db" -Force
  Write-Host 'salva-estado: snapshot de jobs.db gravado.' -ForegroundColor DarkGray
}
exit 0
