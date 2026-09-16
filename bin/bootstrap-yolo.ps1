# PAPIRO SOBERANO - bootstrap YOLO
# Abre o opencode em C:\PAPIRO em modo YOLO (--auto) com cerebro Muse Spark 1.3 Free OpenCode Zen.
# Atalho grafico no Desktop aponta para este arquivo via wt.exe.

$ErrorActionPreference = 'Stop'
$Raiz = Split-Path -Parent $PSScriptRoot
Set-Location $Raiz

# Fail-closed: forca OAuth/assinatura Zen, evita API key fantasma cobrando por token
$env:ANTHROPIC_API_KEY = ''
$env:ANTHROPIC_AUTH_TOKEN = ''
$env:OPENAI_API_KEY = ''
$env:OPENROUTER_API_KEY = ''
$env:GOOGLE_API_KEY = ''
$env:GEMINI_API_KEY = ''

# UTF-8 total (hooks morrem em cp1252) - PRD §3.2
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = $Raiz
$env:PAPIRO_HOME = $Raiz
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host ''
Write-Host '  PAPIRO SOBERANO' -ForegroundColor Cyan
Write-Host '  AGENTE AUTONOMO (LXXX) + PAPIRO PRD (88 RFs) - 100% fiel' -ForegroundColor DarkGray
Write-Host '  opencode --auto (YOLO) + muse-spark-1.3-contributor-free (Zen)' -ForegroundColor DarkGray
Write-Host "  $Raiz" -ForegroundColor DarkGray
Write-Host ''

# Perfil HW P0-P3 §3.3
try {
  $gpu = Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name
  Write-Host "  GPU: $($gpu -join ' | ')" -ForegroundColor DarkGray
} catch { Write-Host '  GPU: P0 (so CPU)' -ForegroundColor DarkGray }
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { Write-Host '  Perfil: P1 (NVIDIA)' -ForegroundColor Green }
else { Write-Host '  Perfil: P0 (CPU) - ver papiro.toml' -ForegroundColor Yellow }
Write-Host ''

$opencode = Get-Command opencode -ErrorAction SilentlyContinue
if (-not $opencode) {
  Write-Host '  opencode nao encontrado no PATH.' -ForegroundColor Red
  Write-Host '  Instale: npm i -g opencode-ai' -ForegroundColor Yellow
  Read-Host '  Enter para sair'
  exit 1
}

Write-Host "  opencode: $($opencode.Source)" -ForegroundColor DarkGray
Write-Host "  modelo: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free Zen)" -ForegroundColor DarkGray
Write-Host '  agente: papiro-soberano (primary) + 12 subagentes' -ForegroundColor DarkGray
Write-Host '  Pressione Ctrl+C para sair. Reabra pelo icone para voltar em YOLO.' -ForegroundColor DarkGray
Write-Host ''

# YOLO = --auto (aprova tudo nao negado) + modelo + agente fixos
& $opencode.Source --auto --model "opencode/muse-spark-1.3-contributor-free" --agent "papiro-soberano"
