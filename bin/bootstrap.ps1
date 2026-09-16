# PAPIRO - bootstrap completo §14.3 (instalador). Uso unico; dia a dia use bootstrap-yolo.ps1
$ErrorActionPreference = 'Stop'
$Raiz = 'C:\PAPIRO'
Set-Location $Raiz
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'; $env:PYTHONUTF8 = '1'

Write-Host '[1/8] Windows, ESU, espaco, LongPaths...' -ForegroundColor Cyan
$os = (Get-CimInstance Win32_OperatingSystem).Caption
Write-Host "  SO: $os"
$lp = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name LongPathsEnabled -ErrorAction SilentlyContinue
if (-not $lp -or $lp.LongPathsEnabled -ne 1) { Write-Host '  AVISO: ative LongPathsEnabled (admin) p/ caminhos >260' -ForegroundColor Yellow }
else { Write-Host '  LongPaths: OK' -ForegroundColor Green }

Write-Host '[2/8] Gerenciadores (winget presente?)...' -ForegroundColor Cyan
Get-Command winget -ErrorAction SilentlyContinue | Out-Null
Get-Command python -ErrorAction Stop | Out-Null
& python --version

Write-Host '[3/8] Motores pip (engines.lock)...' -ForegroundColor Cyan
& python -m pip install --quiet --upgrade pip
& python -m pip install --quiet -e ./core
& python -m pip install --quiet pikepdf pdfplumber segno openpyxl structlog watchdog img2pdf pymupdf4llm pyyaml

Write-Host '[4/8] Ambiente Python...' -ForegroundColor Cyan
& python -c "import fitz,pikepdf,pypdf,pdfplumber,segno,openpyxl; print('  libs PDF OK')"

Write-Host '[5/8] Perfil hardware -> papiro.toml...' -ForegroundColor Cyan
& python -c "import sys; sys.path.insert(0,'core'); from papiro_core import engines; print('  perfil:', engines.perfil_hardware())"

Write-Host '[6/8] Modelos/fontes: OFL via sistema; modelos locais opcionais (Ollama P1-P3)...' -ForegroundColor Cyan

Write-Host '[7/8] MCP + hooks registrados (opencode.json, .mcp.json, .claude/hooks)...' -ForegroundColor Cyan
Test-Path './opencode.json' | Out-Null; Test-Path './.mcp.json' | Out-Null

Write-Host '[8/8] /papiro-status + fumaca 20 testes...' -ForegroundColor Cyan
& python -m pytest core/tests/test_fumaca.py -q --no-header --tb=short
Write-Host ''
Write-Host 'BOOTSTRAP OK. Use o icone PAPIRO Soberano (YOLO) no Desktop.' -ForegroundColor Green
