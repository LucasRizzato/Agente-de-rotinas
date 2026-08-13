@echo off
:: Adiciona o Agente Financeiro Perinity ao Agendador de Tarefas do Windows
:: Executa a cada hora em horario comercial (08h as 19h)

set TASK_NAME=Guardiao-Financeiro-Perinity
set SCRIPT_PATH=%~dp0run_finance.bat

echo ============================================
echo  Agendando tarefa: %TASK_NAME%
echo  Horario: a cada hora, das 08:00 as 19:00
echo ============================================
echo.

:: Remove tarefa antiga se existir
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Cria nova tarefa
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%SCRIPT_PATH%\"" ^
  /sc HOURLY ^
  /st 08:00 ^
  /ru "%USERNAME%" ^
  /rl HIGHEST ^
  /f

if errorlevel 1 (
    echo [ERRO] Falha ao criar tarefa. Execute como Administrador.
    pause
    exit /b 1
)

echo.
echo [OK] Tarefa agendada com sucesso!
echo      Para alterar o horario, edite este arquivo e execute novamente.
echo      ^(O Agendador do Windows nao limita horario final facilmente;
echo       ajuste em Agendador de Tarefas ^> %TASK_NAME% ^> Disparadores se quiser.^)
echo.
echo Para ver a tarefa: Agendador de Tarefas ^> Biblioteca ^> %TASK_NAME%
echo Para executar agora: schtasks /run /tn "%TASK_NAME%"
echo.
pause
