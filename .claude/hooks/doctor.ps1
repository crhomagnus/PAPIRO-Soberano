# PAPIRO hook doctor - SessionStart: binarios, versoes, perfil, disco (nao bloqueia)
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Host 'PAPIRO doctor: verificando ambiente...' -ForegroundColor DarkGray
& python -m papiro_core.cli status 2>$null | Select-Object -First 5
try {
  Set-Location 'C:\PAPIRO\core'
  & python -c "import sys; sys.path.insert(0,'.'); from papiro_core import engines; print('perfil HW:', engines.perfil_hardware())"
} catch {}
$disk = Get-PSDrive C | Select-Object -ExpandProperty Free
Write-Host ("disco C livre: {0:N1} GB" -f ($disk / 1GB)) -ForegroundColor DarkGray
exit 0
