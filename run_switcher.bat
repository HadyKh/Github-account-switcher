@echo off
cd /d "%~dp0"
if "%~1"=="" (
    start "" pythonw "%~dp0main.py"
) else (
    python "%~dp0main.py" %*
)
