@echo off
:: Check Administrator Privileges
net session >nul 2>&1
if %errorLevel% == 0 (
    start "" pythonw "%~dp0main.py" %*
) else (
    powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -FilePath 'pythonw' -ArgumentList '\"%~dp0main.py\" %*' -Verb RunAs -WindowStyle Hidden"
)
exit /b
