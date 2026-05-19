@echo off
:: Adiciona o Guardiao ao Agendador de Tarefas do Windows
:: Executa todos os dias as 08:00

set TASK_NAME=Guardiao-Obsidian-AI
set SCRIPT_PATH=%~dp0run.bat
set RUN_TIME=08:00

echo ============================================
echo  Agendando tarefa: %TASK_NAME%
echo  Horario: diariamente as %RUN_TIME%
echo ============================================
echo.

:: Remove tarefa antiga se existir
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Cria nova tarefa
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%SCRIPT_PATH%\"" ^
  /sc DAILY ^
  /st %RUN_TIME% ^
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
echo.
echo Para ver a tarefa: Agendador de Tarefas ^> Biblioteca ^> %TASK_NAME%
echo Para executar agora: schtasks /run /tn "%TASK_NAME%"
echo.
pause
