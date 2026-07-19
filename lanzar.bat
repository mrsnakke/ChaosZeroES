@echo off
python app.py
if errorlevel 1 (
    echo.
    echo Error al ejecutar. Instala dependencias con instalar.bat
    pause
)
