@echo off
echo ============================================
echo  GUARDIAO - Setup
echo ============================================

:: Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado. Instale em https://python.org
    pause
    exit /b 1
)

:: Instala dependencias
echo.
echo [1/3] Instalando dependencias Python...
python -m pip install --upgrade pip -q
python -m pip install -r "%~dp0requirements.txt"

:: Cria .env se nao existir
echo.
if not exist "%~dp0.env" (
    echo [2/3] Criando .env a partir do exemplo...
    copy "%~dp0.env.example" "%~dp0.env"
    echo.
    echo  ** IMPORTANTE **
    echo  Abra o arquivo .env e preencha:
    echo    - ANTHROPIC_API_KEY
    echo    - TELEGRAM_BOT_TOKEN  ^(obtenha com @BotFather no Telegram^)
    echo    - TELEGRAM_CHAT_ID   ^(rode python bot.py e envie /start^)
    echo.
) else (
    echo [2/3] Arquivo .env ja existe.
)

echo [3/3] Testando leitura do vault ^(dry-run^)...
python "%~dp0agent.py" --dry-run

echo.
echo ============================================
echo  Setup concluido! Proximos passos:
echo  1. Edite o .env com suas chaves
echo  2. Execute: run_bot.bat     ^(bot interativo^)
echo  3. Execute: schedule.bat    ^(relatorio diario^)
echo ============================================
pause
