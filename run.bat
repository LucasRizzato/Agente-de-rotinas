@echo off
:: Executa o agente e salva log com timestamp
set LOG_DIR=%~dp0logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set LOG_FILE=%LOG_DIR%\guardiao_%date:~6,4%%date:~3,2%%date:~0,2%.log

echo Iniciando Guardiao... >> "%LOG_FILE%"
python "%~dp0agent.py" >> "%LOG_FILE%" 2>&1
echo. >> "%LOG_FILE%"
