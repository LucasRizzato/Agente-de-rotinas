@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

echo ============================================
echo  Reprocessando notas ja registradas
echo  ^(preenche Valor Liquido e confere o mes^)
echo ============================================
echo.

python "%~dp0reprocess_existing.py"

echo.
pause
