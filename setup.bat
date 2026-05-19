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
python -m pip install -r requirements.txt

:: Cria .env se nao existir
echo.
if not exist ".env" (
    echo [2/3] Criando .env a partir do exemplo...
    copy ".env.example" ".env"
    echo       IMPORTANTE: Abra o arquivo .env e preencha suas chaves antes de continuar!
) else (
    echo [2/3] Arquivo .env ja existe.
)

echo.
echo [3/3] Testando leitura do vault (dry-run)...
python agent.py --dry-run

echo.
echo ============================================
echo  Setup concluido! Proximo passo:
echo  1. Edite o arquivo .env com suas chaves
echo  2. Execute: run.bat  (para testar)
echo  3. Execute: schedule.bat  (para agendar)
echo ============================================
pause
