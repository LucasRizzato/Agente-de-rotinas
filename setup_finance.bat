@echo off
cd /d "%~dp0"

echo ============================================
echo  AGENTE FINANCEIRO PERINITY - Setup
echo ============================================

:: Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado. Instale em https://python.org
    pause
    exit /b 1
)

echo.
echo [1/4] Instalando dependencias Python...
python -m pip install --upgrade pip -q
python -m pip install -r "%~dp0requirements.txt"

echo.
if not exist "%~dp0.env" (
    echo [2/4] Criando .env a partir do exemplo...
    copy "%~dp0.env.example" "%~dp0.env"
) else (
    echo [2/4] Arquivo .env ja existe. Confira se as variaveis abaixo estao
    echo       preenchidas ^(compare com .env.example^):
    echo         GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH,
    echo         PJ_INBOX_ADDRESS, FORNECEDOR_INBOX_ADDRESS,
    echo         PJ_NOTAS_BASE_PATH, FORNECEDOR_NOTAS_BASE_PATH,
    echo         CONTROL_SHEET_PATH
)

echo.
echo [3/4] Credenciais do Gmail ^(OAuth^):
echo   a. Acesse https://console.cloud.google.com/ e crie/selecione um projeto
echo   b. Ative a "Gmail API" ^(APIs ^& Services ^> Library^)
echo   c. Crie uma credencial OAuth do tipo "App para Computador"
echo      ^(APIs ^& Services ^> Credentials ^> Create Credentials^)
echo   d. Baixe o JSON e salve como "credentials.json" nesta pasta
echo      ^(ou aponte GMAIL_CREDENTIALS_PATH no .env para o caminho escolhido^)
echo.
echo   ** IMPORTANTE ** Preencha tambem no .env:
echo      - ANTHROPIC_API_KEY
echo      - TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID ^(rode python bot.py e envie /start^)
echo      - Os caminhos das pastas de notas fiscais e da planilha de controle
echo.
pause

echo.
echo [4/4] Testando conexao com o Gmail ^(dry-run, abre o navegador p/ login^)...
set PYTHONIOENCODING=utf-8
python "%~dp0finance_agent.py" --dry-run

echo.
echo ============================================
echo  Setup concluido! Proximos passos:
echo  1. Confira o resultado do dry-run acima
echo  2. Execute: run_finance.bat      ^(roda uma vez^)
echo  3. Execute: schedule_finance.bat ^(agenda execucoes automaticas^)
echo ============================================
pause
