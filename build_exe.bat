@echo off
title Build WindowsTimeAutoUpdate EXE

echo [*] Generating icon...
python -c "from tray_icon import create_default_icon_image; img = create_default_icon_image(128, 128); img.save('app_icon.ico', format='ICO', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128)])"

echo [*] Compiling Native WindowsTimeAutoUpdate.exe...
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /target:winexe /optimize+ /platform:anycpu /win32icon:app_icon.ico /out:WindowsTimeAutoUpdate.exe launcher.cs

if %errorlevel% equ 0 (
    echo.
    echo [+] Successfully created WindowsTimeAutoUpdate.exe!
) else (
    echo.
    echo [-] Compilation failed.
)
pause
