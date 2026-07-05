@echo off
REM ===== Planungshelfer starten =====
REM venv liegt BEWUSST ausserhalb von OneDrive (unter %LOCALAPPDATA%),
REM damit OneDrive nicht tausende venv-Dateien synchronisiert.
cd /d "%~dp0"

set "VENV=%LOCALAPPDATA%\venvs\Planungshelfer"

if not exist "%VENV%\Scripts\python.exe" (
    echo [Setup] Erstelle virtuelle Umgebung unter %VENV% ...
    python -m venv "%VENV%"
    call "%VENV%\Scripts\activate.bat"
    echo [Setup] Installiere Abhaengigkeiten...
    python -m pip install --upgrade pip >nul
    python -m pip install -r requirements.txt
) else (
    call "%VENV%\Scripts\activate.bat"
)

echo.
echo ============================================
echo   Planungshelfer:  http://127.0.0.1:5005
echo   (Fenster offen lassen; STRG+C zum Beenden)
echo ============================================
echo.

REM Browser automatisch oeffnen
start "" http://127.0.0.1:5005

python app.py
pause
