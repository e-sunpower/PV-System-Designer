@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo   E-SUN POWER PV System Designer V153.22
echo   Servidor local: http://127.0.0.1:8765
echo ================================================
echo.

echo Iniciando servidor local...
start "E-SUN POWER - SERVIDOR LOCAL" /min cmd /c "python server.py"

timeout /t 2 /nobreak >nul

echo Abriendo E-SUN POWER en el navegador...
start "" "http://127.0.0.1:8765"
echo.
echo No cierres la ventana del servidor mientras uses la aplicacion.
echo Para detenerla, cierra la ventana negra del servidor.
endlocal
