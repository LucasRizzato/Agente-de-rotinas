@echo off
:: Executa o Agente Financeiro Perinity e salva log com timestamp

:: Fixa a pasta de trabalho na pasta deste arquivo. Sem isso, quando o
:: Agendador de Tarefas do Windows roda esta tarefa (em vez de você dar
:: duplo clique), a pasta de trabalho vira C:\Windows\System32 por padrão,
:: e o Python não acha credentials.json/token.json/.env nem grava o log
:: onde deveria — falha sempre que rodar sozinho, mesmo funcionando quando
:: testado manualmente.
cd /d "%~dp0"

set LOG_DIR=%~dp0logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

:: Usa o PowerShell para o carimbo de data — %date% fatiado por posição de
:: caractere quebra dependendo da configuração regional do Windows (ex: se
:: aparecer o dia da semana antes da data).
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set LOG_DATE=%%i
set LOG_FILE=%LOG_DIR%\financeiro_%LOG_DATE%.log

:: Força o Python a usar UTF-8 na saída — sem isso, redirecionar a saída
:: para um arquivo (como estamos fazendo aqui) faz o Windows usar uma
:: codificação antiga que não sabe representar os caracteres usados nas
:: mensagens, e quebra tudo com UnicodeEncodeError antes de processar
:: qualquer e-mail.
set PYTHONIOENCODING=utf-8

echo Iniciando Agente Financeiro Perinity... >> "%LOG_FILE%"
python "%~dp0finance_agent.py" >> "%LOG_FILE%" 2>&1
echo. >> "%LOG_FILE%"
