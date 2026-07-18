@echo off
title ChaosZero ES - Instalador
color 0A
echo.
echo  ========================================
echo   ChaosZero ES - Instalacion
echo  ========================================
echo.
echo  Este script instala las dependencias necesarias.
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [!] Python no encontrado.
    echo  [!] Descarga Python 3.10+ desde: https://python.org
    echo  [!] Marca "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

echo  [OK] Python encontrado:
python --version
echo.

echo  [1/2] Instalando numpy...
pip install numpy --quiet
if errorlevel 1 (
    echo  [ERROR] Fallo la instalacion de numpy.
    pause
    exit /b 1
)
echo  [OK] numpy instalado.

echo.
echo  [2/2] Verificando instalacion...
python -c "import numpy; print('  numpy:', numpy.__version__)"
if errorlevel 1 (
    echo  [ERROR] numpy no funciona correctamente.
    pause
    exit /b 1
)

echo.
echo  ========================================
echo   Instalacion completada!
echo  ========================================
echo.
echo  Ahora ejecuta: lanzar.bat
echo.
pause
