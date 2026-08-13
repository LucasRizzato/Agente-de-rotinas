@echo off
:: Executa o Agente Financeiro Perinity e salva log com timestamp
set LOG_DIR=%~dp0logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set LOG_FILE=%LOG_DIR%\financeiro_%date:~6,4%%date:~3,2%%date:~0,2%.log

echo Iniciando Agente Financeiro Perinity... >> "%LOG_FILE%"
python "%~dp0finance_agent.py" >> "%LOG_FILE%" 2>&1
echo. >> "%LOG_FILE%"
