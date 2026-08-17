@echo off
cd /d "%~dp0"

:: Adiciona o Agente Financeiro Perinity ao Agendador de Tarefas do Windows.
:: Executa a cada hora, a partir das 08:00. Nao precisa de senha nem de
:: "Executar como administrador" - a tarefa roda como o proprio usuario,
:: oculta (sem janela), e nao para se o notebook estiver na bateria.

echo ============================================
echo  Agendando tarefa: Guardiao-Financeiro-Perinity
echo  Horario: a cada hora, a partir das 08:00
echo ============================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0register_task.ps1"

if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao criar a tarefa - veja a mensagem acima.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Para alterar o horario ou os dias, abra o Agendador de Tarefas do
echo  Windows e edite a tarefa "Guardiao-Financeiro-Perinity" ^(busque
echo  "Agendador de Tarefas" no menu Iniciar^).
echo.
echo  Para testar agora, sem esperar a proxima hora cheia:
echo    schtasks /run /tn "Guardiao-Financeiro-Perinity"
echo ============================================
pause
