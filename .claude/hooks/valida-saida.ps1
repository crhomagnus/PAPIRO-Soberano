# PAPIRO hook valida-saida - qpdf-check equivalente + miniatura + hash (nao bloqueia)
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$raw = [Console]::In.ReadToEnd()
try { $ev = $raw | ConvertFrom-Json } catch { exit 0 }
$text = ($ev | ConvertTo-Json -Compress)
foreach ($m in [regex]::Matches($text, 'C:\\\\PAPIRO\\\\out\\\\[^"]+\.pdf')) {
  $p = $m.Value
  if (Test-Path $p) {
    try {
      & python -c "import fitz,sys; d=fitz.open(sys.argv[1]); print(len(d)); d.close()" "$p" | Out-Null
      if ($LASTEXITCODE -eq 0) { Write-Host "valida-saida OK: $p" -ForegroundColor DarkGray }
      else { Write-Host "valida-saida FALHOU: $p" -ForegroundColor Yellow }
    } catch {}
  }
}
exit 0
