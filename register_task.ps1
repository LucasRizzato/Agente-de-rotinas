# Cadastra a tarefa agendada do Agente Financeiro Perinity sem precisar de
# senha nem de privilégios de administrador: roda como o próprio usuário
# (só quando ele estiver logado), oculta (sem janela visível) e sem parar
# se o notebook estiver na bateria.

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$batPath = Join-Path $scriptDir "run_finance.bat"
$taskName = "Guardiao-Financeiro-Perinity"

try {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

    $action = New-ScheduledTaskAction -Execute $batPath -WorkingDirectory $scriptDir

    $startTime = Get-Date -Hour 8 -Minute 0 -Second 0
    # O Agendador de Tarefas rejeita [TimeSpan]::MaxValue (gera uma duração
    # fora do intervalo aceito pelo schema XML dele). 10 anos já cobre
    # qualquer uso real como "repete pra sempre".
    $trigger = New-ScheduledTaskTrigger -Once -At $startTime `
        -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)

    $settings = New-ScheduledTaskSettingsSet `
        -Hidden `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew

    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Settings $settings -Description "Agente Financeiro Perinity - roda de hora em hora" | Out-Null

    Write-Host ""
    Write-Host "[OK] Tarefa agendada com sucesso (sem precisar de senha)."
    Write-Host ""
    Write-Host "Status:"
    Get-ScheduledTaskInfo -TaskName $taskName | Format-List NextRunTime, LastRunTime, LastTaskResult
}
catch {
    Write-Host ""
    Write-Host "[ERRO] Nao foi possivel agendar a tarefa:"
    Write-Host $_.Exception.Message
    exit 1
}
