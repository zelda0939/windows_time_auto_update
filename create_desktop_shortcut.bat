@echo off
setlocal
cd /d "%~dp0"
title Create Desktop Shortcut

echo ========================================================
echo   Windows Time Auto Update - Create Desktop Shortcut
echo ========================================================
echo.
echo [*] Creating Desktop Shortcut...

powershell -NoProfile -ExecutionPolicy Bypass -Command "$name = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('V2luZG93cyDntrLot6/oh6rli5XmoKHmmYLlt6XlhbcubG5r')); $ws = New-Object -ComObject WScript.Shell; $desktop = [System.Environment]::GetFolderPath('Desktop'); $shortcutPath = Join-Path $desktop $name; $s = $ws.CreateShortcut($shortcutPath); $s.TargetPath = Join-Path $PWD 'WindowsTimeAutoUpdate.exe'; $s.WorkingDirectory = $PWD.Path; if (Test-Path 'app_icon.ico') { $s.IconLocation = (Join-Path $PWD 'app_icon.ico') + ',0' }; $s.Save(); Write-Host '[+] Desktop Shortcut Created Successfully!'"

echo.
pause
