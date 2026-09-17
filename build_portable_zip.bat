@echo off
title Build WindowsTimeAutoUpdate Portable Edition
echo =================================================================
echo  Windows 網路自動校時工具 - 免安裝綠色便攜包一鍵建置
echo =================================================================

echo [*] 正在確認啟動器 WindowsTimeAutoUpdate.exe...
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /target:winexe /optimize+ /platform:anycpu /win32icon:app_icon.ico /out:WindowsTimeAutoUpdate.exe launcher.cs

if %errorlevel% neq 0 (
    echo [-] 啟動器編譯失敗！
    pause
    exit /b %errorlevel%
)

echo.
echo [*] 正在建置獨立精簡 Runtime 並打包 ZIP...
python create_portable_package.py

echo.
pause
