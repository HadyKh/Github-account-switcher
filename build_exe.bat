@echo off
cd /d "%~dp0"
echo Building GitHubAccountSwitcher.exe ...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "GitHubAccountSwitcher" --distpath . main.py
echo.
if exist "GitHubAccountSwitcher.exe" (
    echo Build complete! Output: %~dp0GitHubAccountSwitcher.exe
) else (
    echo Build failed!
)
