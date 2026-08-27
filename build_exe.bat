@echo off
chcp 65001 >nul
title 打包 Windows 網路自動校時工具為獨立 EXE

echo 正在檢查 PyInstaller...
python -m pip install pyinstaller Pillow pystray

echo.
echo 正在編譯打包 WindowsTimeAutoUpdate.exe...
pyinstaller --noconsole --onefile --name "WindowsTimeAutoUpdate" --uac-admin main.py

echo.
echo 打包完成！請至 dist 目錄查看 WindowsTimeAutoUpdate.exe
pause
