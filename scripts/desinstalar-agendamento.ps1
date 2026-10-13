# Remove as tarefas do Muvim do Agendador do Windows. Os dados em dados\ continuam onde estão.
foreach ($t in 'Muvim - Servidor', 'Muvim - Coleta') {
    if (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $t -Confirm:$false
        Write-Host "Removida: $t"
    }
}
