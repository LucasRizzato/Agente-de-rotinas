@echo off
:: Inicia o Guardiao Bot em loop (reinicia se cair)
title Guardiao Bot

:loop
echo [%time%] Iniciando bot...
python "%~dp0bot.py"
echo [%time%] Bot encerrado. Reiniciando em 10 segundos...
timeout /t 10 /nobreak >nul
goto loop
