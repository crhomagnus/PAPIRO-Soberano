# PAPIRO hook pede-revisao - marca saida de designer/compositor como pendente de revisao (nao bloqueia)
$ErrorActionPreference = 'SilentlyContinue'
$flag = 'C:\PAPIRO\work\_revisao_pendente.flag'
Set-Content -Path $flag -Value ("pendente em " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')) -Force
Write-Host 'pede-revisao: saida marcada como pendente de pdf-revisor-qa.' -ForegroundColor DarkGray
exit 0
