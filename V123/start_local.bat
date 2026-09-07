@echo off
setlocal
cd /d "%~dp0"
REM Cerrar únicamente el proceso que esté escuchando en el puerto 8765,
REM para evitar que el navegador siga usando una versión antigua del servidor.
for /f "tokens=5" %%P in ('netstat -ano ^| findstr LISTENING ^| findstr :8765') do (
  taskkill /F /PID %%P >nul 2>&1
)
timeout /t 1 /nobreak >nul
start "E-SUN POWER V90" http://localhost:8765
python server.py
pause
