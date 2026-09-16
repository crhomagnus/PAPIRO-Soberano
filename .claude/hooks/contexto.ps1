# PAPIRO hook contexto - injeta brandkit ativo + perfil HW no prompt (nao bloqueia)
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$perfil = 'P0'
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { $perfil = 'P1' }
$bk = Get-ChildItem 'C:\PAPIRO\brandkits\*\tokens.yaml' -ErrorAction SilentlyContinue | Select-Object -First 1
$bkNome = if ($bk) { $bk.Directory.Name } else { 'padrao' }
$extra = @{
  papiro_contexto = @{
    perfil_hw = $perfil
    brandkit = $bkNome
    modelo = 'opencode/muse-spark-1.3-contributor-free'
    regras = 'pt-BR, 1 passo por vez; nunca sobrescrever entradas; tudo em work/out; sem qa APROVADO sem entrega'
  }
}
Write-Output ($extra | ConvertTo-Json -Compress -Depth 4)
exit 0
