@echo off
chcp 65001 >nul
echo Instalando PyInstaller...
pip install pyinstaller
echo.
echo Creando ejecutable + datos en dist\ChaosZeroES...
if exist dist\ChaosZeroES rmdir /s /q dist\ChaosZeroES
pyinstaller --onedir --windowed --name "ChaosZeroES" app.py
if not exist dist\ChaosZeroES (
    echo ERROR: Fallo la compilacion
    pause
    exit /b 1
)
echo.
echo Copiando archivos de datos...
copy glossary.json dist\ChaosZeroES\ >nul
copy translations.tsv dist\ChaosZeroES\ >nul
if exist app_config.json copy app_config.json dist\ChaosZeroES\ >nul
echo.
echo ============================================
echo  LISTO! Carpeta: dist\ChaosZeroES\
echo  Copia toda la carpeta a tu amigo.
echo  El .exe funciona sin instalar nada.
echo ============================================
pause
