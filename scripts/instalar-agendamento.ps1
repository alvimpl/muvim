# Registra duas tarefas no Agendador do Windows, só para o usuário atual (não precisa de administrador):
#   Muvim - Servidor : sobe o site local (http://localhost:8790) ao entrar no Windows
#   Muvim - Coleta   : coleta ao entrar no Windows e todo dia às 10h; se o PC estava desligado, roda quando ligar
# Para remover: scripts\desinstalar-agendamento.ps1

$ErrorActionPreference = 'Stop'
$raiz = Split-Path -Parent $PSScriptRoot
$py = (Get-Command python -ErrorAction Stop).Source
$pyw = Join-Path (Split-Path $py) 'pythonw.exe'
if (-not (Test-Path $pyw)) { $pyw = $py }
$usuario = "$env:USERDOMAIN\$env:USERNAME"

$cfg = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
       -ExecutionTimeLimit (New-TimeSpan -Hours 3) -MultipleInstances IgnoreNew

# Servidor
$acaoS = New-ScheduledTaskAction -Execute $pyw -Argument "`"$raiz\servidor.py`"" -WorkingDirectory $raiz
$gatS = New-ScheduledTaskTrigger -AtLogOn -User $usuario
$cfgS = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'Muvim - Servidor' -Action $acaoS -Trigger $gatS -Settings $cfgS `
    -Description 'Site local do Muvim em http://localhost:8790' -Force | Out-Null

# Coleta: ao entrar (com 3 min de folga para a rede subir) e diariamente
$acaoC = New-ScheduledTaskAction -Execute $pyw -Argument "`"$raiz\coletar.py`"" -WorkingDirectory $raiz
$gatLogon = New-ScheduledTaskTrigger -AtLogOn -User $usuario
$gatLogon.Delay = 'PT3M'
$gatDia = New-ScheduledTaskTrigger -Daily -At 10:00
Register-ScheduledTask -TaskName 'Muvim - Coleta' -Action $acaoC -Trigger @($gatLogon, $gatDia) -Settings $cfg `
    -Description 'Coleta diaria de lancamentos do Muvim' -Force | Out-Null

Write-Host 'Tarefas registradas: "Muvim - Servidor" e "Muvim - Coleta".'
