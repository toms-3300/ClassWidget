@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Installation failed. Please copy the error message.
) else (
    echo Installation complete. You can launch ClassWidget now.
)
pause
