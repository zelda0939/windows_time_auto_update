@echo off
:: Create Desktop Shortcut pointing to WindowsTimeAutoUpdate.exe
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $desktop = [System.Environment]::GetFolderPath('Desktop'); $s = $ws.CreateShortcut(\"$desktop\Windows 網路自動校時工具.lnk\"); $s.TargetPath = \"$PSScriptRoot\WindowsTimeAutoUpdate.exe\"; $s.WorkingDirectory = \"$PSScriptRoot\"; if (Test-Path \"$PSScriptRoot\app_icon.ico\") { $s.IconLocation = \"$PSScriptRoot\app_icon.ico,0\" }; $s.Save(); Write-Host '[+] 桌面捷徑已成功建立！'"
pause
