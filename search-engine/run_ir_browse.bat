@echo off
cd /d "%~dp0"
echo.
echo  IR FYP Browse Server
echo  Opening http://localhost:9090/
echo.
python ir_browse_server.py
pause
