@echo off
chcp 65001 >nul

start "" pythonw "%~dp0main.py" %*
exit /b
