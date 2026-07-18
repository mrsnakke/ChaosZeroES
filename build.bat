@echo off
title ChaosZero ES - Construir EXE
color 0A
echo.
echo  ========================================
echo   ChaosZero ES - Construir Ejecutable
echo  ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [!] Python no encontrado.
    pause
    exit /b 1
)

:: Check/Install PyInstaller
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo  Instalando PyInstaller...
    pip install pyinstaller --quiet
    if errorlevel 1 (
        echo  [!] Error instalando PyInstaller.
        pause
        exit /b 1
    )
)

echo  [1/3] Construyendo EXE...
echo.

set "SCRIPT_DIR=%~dp0"

python -m PyInstaller ^
    -F ^
    -w ^
    -n "ChaosZeroES" ^
    --distpath "%SCRIPT_DIR%dist" ^
    --workpath "%SCRIPT_DIR%build" ^
    --specpath "%SCRIPT_DIR%" ^
    --hidden-import "rebuild_ko_to_es" ^
    --hidden-import "extract_and_translate" ^
    --hidden-import "extract_text" ^
    --hidden-import "translate_incremental" ^
    --hidden-import "numpy" ^
    --hidden-import "numpy.core._methods" ^
    --hidden-import "numpy.lib.format" ^
    "%SCRIPT_DIR%app.py"

if errorlevel 1 (
    echo.
    echo  [!] Error al construir el EXE.
    pause
    exit /b 1
)

echo.
echo  [2/3] Verificando...
if exist "%SCRIPT_DIR%dist\ChaosZeroES.exe" (
    echo  OK: dist\ChaosZeroES.exe
) else (
    echo  [!] EXE no encontrado.
    pause
    exit /b 1
)

echo.
echo  [3/3] Limpiando archivos temporales...
rd /s /q "%SCRIPT_DIR%build" 2>nul
del "%SCRIPT_DIR%ChaosZeroES.spec" 2>nul

echo.
echo  ========================================
echo   EXE listo: dist\ChaosZeroES.exe
echo  ========================================
echo.
echo  Para compartir: copiar solo ChaosZeroES.exe
echo  (No necesita Python ni nada instalado)
echo.
pause
