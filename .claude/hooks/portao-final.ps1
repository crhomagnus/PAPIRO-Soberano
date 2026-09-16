# PAPIRO hook portao-final - BLOQUEIA Stop sem qa-report.json APROVADO (PRD §7.4 + §11)
$ErrorActionPreference = 'Stop'
$outs = Get-ChildItem 'C:\PAPIRO\out' -Recurse -Filter 'qa-report.json' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $outs) { exit 0 }  # nada entregue ainda: nao bloqueia conversa
try {
  $qa = Get-Content $outs.FullName -Raw | ConvertFrom-Json
  $status = $qa.status
  if (-not $status -and $qa.qa) { $status = $qa.qa.status }
  if ($status -ne 'APROVADO') {
    Write-Host "BLOQUEADO portao-final: ultimo QA = $status em $($outs.FullName). Rode qa_run ate APROVADO." -ForegroundColor Red
    exit 2
  }
} catch { exit 0 }
exit 0
