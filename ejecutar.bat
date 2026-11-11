@echo off
chcp 65001 > nul
title Renombrador Multimedia
echo Iniciando Renombrador Multimedia...
python "%~dp0main.py" %*
if errorlevel 1 (
    echo.
    echo Ha ocurrido un error al iniciar el programa.
    pause
)

