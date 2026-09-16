# PAPIRO hook guarda-originais - BLOQUEIA escrita fora de work/out e sobre entradas (PRD §7.4)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$raw = [Console]::In.ReadToEnd()
try { $ev = $raw | ConvertFrom-Json -ErrorAction Stop } catch { exit 0 }
$tool = $ev.tool_name
if ($tool -notin @('Write', 'Edit', 'PowerShell', 'mcp__papiro')) {
  if ($tool -notlike 'mcp__papiro*') { exit 0 }
}
$input = ($ev.tool_input | ConvertTo-Json -Compress)
# bloqueia rm recursivo / format / del sistema
if ($input -match '(?i)rm\s+-Recurse|Remove-Item.*-Recurse.*C:\\|Format-Volume|diskpart') {
  Write-Host 'BLOQUEADO guarda-originais: exclusao recursiva proibida.' -ForegroundColor Red
  exit 2
}
# permite apenas C:\PAPIRO\work e C:\PAPIRO\out (+ docs leitura)
if ($input -match '[A-Z]:\\') {
  $paths = [regex]::Matches($input, '[A-Z]:\\\\[^"]+') | ForEach-Object { $_.Value }
  foreach ($p in $paths) {
    if ($p -like 'C:\PAPIRO\work\*' -or $p -like 'C:\PAPIRO\out\*' -or $p -like 'C:\PAPIRO\logs\*' -or $p -like 'C:\PAPIRO\work*' -or $p -like 'C:\PAPIRO\out*') { continue }
    if ($p -like 'C:\PAPIRO\docs\*' -or $p -like 'C:\PAPIRO\.opencode\*' -or $p -like 'C:\PAPIRO\core\*') { continue }
    if ($tool -in @('Write', 'Edit') -or $tool -like 'mcp__papiro*') {
      Write-Host "BLOQUEADO guarda-originais: escrita fora de work/out: $p" -ForegroundColor Red
      exit 2
    }
  }
}
exit 0
