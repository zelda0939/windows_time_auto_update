@echo off
setlocal
cd /d "%~dp0"
title Windows Time Auto Update - Build Portable Package

echo ========================================================
echo   Windows Time Auto Update - Build Portable Package
echo ========================================================
echo.

:: 1. Check Python
set "PY_CMD=python"
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py -3 --version >nul 2>&1
    if %errorlevel% equ 0 (
        set "PY_CMD=py -3"
    ) else (
        echo [ERROR] Python was not found in system PATH.
        echo Please ensure Python 3 is installed and added to PATH.
        pause
        exit /b 1
    )
)

:: 2. Compile C# Launcher if csc.exe exists
if exist launcher.cs (
    echo [*] Checking and compiling Native WindowsTimeAutoUpdate.exe...
    if exist "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe" (
        "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /target:winexe /optimize+ /platform:anycpu /win32icon:app_icon.ico /out:WindowsTimeAutoUpdate.exe launcher.cs >nul 2>&1
    ) else if exist "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe" (
        "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe" /target:winexe /optimize+ /platform:anycpu /win32icon:app_icon.ico /out:WindowsTimeAutoUpdate.exe launcher.cs >nul 2>&1
    )
)

:: 3. Run Build Script
echo [*] Building Portable Runtime and Packaging ZIP...
echo.
%PY_CMD% create_portable_package.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to build portable package.
    pause
    exit /b %errorlevel%
)

echo.
echo ========================================================
echo   [SUCCESS] Portable package created successfully!
echo   Package: WindowsTimeAutoUpdate_Portable.zip
echo ========================================================
echo.
echo Press any key to reveal the package in File Explorer...
pause

if exist "%~dp0WindowsTimeAutoUpdate_Portable.zip" (
    explorer /select,"%~dp0WindowsTimeAutoUpdate_Portable.zip"
)
