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
echo Esta tarefa precisa rodar em segundo plano de verdade ^(mesmo com a
echo tela bloqueada, sem depender de voce estar logado no momento exato^),
echo entao o Windows vai pedir a sua senha do computador agora para
echo guardar de forma protegida no proprio Agendador de Tarefas ^(essa
echo senha NAO fica gravada em nenhum arquivo deste agente^).
echo.
echo Quando aparecer "Type the password for user ...", digite sua senha
echo normal do Windows e aperte Enter ^(a digitacao nao aparece na tela,
echo isso e normal^).
echo.
pause

:: Remove tarefa antiga se existir
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Cria nova tarefa. /rp * faz o Windows pedir a senha na hora, mascarada,
:: e guardar com seguranca no Agendador — sem isso ("Interativo apenas"),
:: a tarefa so roda com uma janela visivel e com a sessao ativa, e morre
:: com erro (STATUS_CONTROL_C_EXIT) se a janela for fechada, a tela travar
:: ou o notebook estiver na bateria nesse horario.
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%SCRIPT_PATH%\"" ^
  /sc HOURLY ^
  /st 08:00 ^
  /ru "%USERNAME%" ^
  /rp * ^
  /rl HIGHEST ^
  /f

if errorlevel 1 (
    echo [ERRO] Falha ao criar tarefa. Confira se:
    echo   - Voce executou este arquivo como Administrador
    echo   - Digitou a senha do Windows corretamente quando foi pedida
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
echo Status atual da tarefa ^(depois que ela rodar, confira o campo
echo "Ultimo Resultado/Last Result": deve ser 0 - qualquer outro numero
echo e erro^):
schtasks /query /tn "%TASK_NAME%" /v /fo LIST
echo.
pause
