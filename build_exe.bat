@echo off
cd /d "%~dp0"
echo Building GitHubAccountSwitcher.exe with custom icon ...
python -m PyInstaller --noconfirm --clean --onefile --windowed --icon "assets\app_icon.ico" --add-data "assets\app_icon.ico;assets" --name "GitHubAccountSwitcher" --distpath . main.py
echo.
if exist "GitHubAccountSwitcher.exe" (
    echo Build complete! Output: %~dp0GitHubAccountSwitcher.exe
) else (
    echo Build failed!
)
