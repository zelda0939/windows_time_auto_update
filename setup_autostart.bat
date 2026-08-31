@echo off
setlocal
cd /d "%~dp0"

:: Check for Administrative privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator privileges to configure Autostart...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

title Windows Time Auto Update - Setup Autostart

echo ========================================================
echo   Windows Time Auto Update - Autostart Setup
echo ========================================================
echo.

if exist launcher.cs (
    echo [*] Compiling Native WindowsTimeAutoUpdate.exe...
    C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /target:winexe /optimize+ /platform:anycpu /win32icon:app_icon.ico /out:WindowsTimeAutoUpdate.exe launcher.cs >nul 2>&1
)

echo [*] Deploying to LocalAppData and configuring Task Scheduler...
python autostart.py

echo.
echo ========================================================
echo  Setup Completed!
echo  The application is now deployed locally and configured
echo  to start on Windows logon with highest privileges.
echo ========================================================
echo.
pause
