@echo off
setlocal enabledelayedexpansion
title ChaosZero ES - Traduccion al Espanol
color 0B

set "SCRIPT_DIR=%~dp0"

:: Si existe el EXE, lanzarlo
if exist "%SCRIPT_DIR%dist\ChaosZeroES.exe" (
    echo Iniciando ChaosZeroES...
    start "" "%SCRIPT_DIR%dist\ChaosZeroES.exe"
    exit /b 0
)

:: Fallback: lanzar con Python
python --version >nul 2>&1
if errorlevel 1 ( echo [!] Python no encontrado. Ejecuta instalar.bat & pause & exit /b 1 )
python -c "import numpy" >nul 2>&1
if errorlevel 1 ( echo [!] numpy no instalado. Ejecuta instalar.bat & pause & exit /b 1 )

echo Iniciando interfaz grafica...
python "%SCRIPT_DIR%app.py"
if errorlevel 1 (
    echo.
    echo [!] Error al iniciar la GUI.
    pause
)
