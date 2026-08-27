# 專案記憶庫 (Project Memory)

## 專案概要
- **專案名稱**：Windows 自動網路校時工具 (Windows Auto Time Synchronizer)
- **目標**：提供一個可自訂更新頻率、可常駐系統匣、具備現代化 UI、支援多 NTP 伺服器並自動校正 Windows 系統時間的桌面工具。

## 關鍵技術決策與架構
- **程式語言與版本**：Python 3.14 + Tkinter + Windows Win32 API (`ctypes.windll.kernel32.SetSystemTime`)
- **NTP 協定**：純 Python RFC 5905 SNTP/NTP 客戶端實作，具備高精準度、網路往返延遲補償（Delay）與時間位移（Offset）計算，支援多伺服器容錯備援。
- **背景排程與智慧校時**：
  - **單調時鐘排程架構 (Monotonic Scheduler)**：排程器與倒數計時全面採用 `time.monotonic()` 物理單調計時，完全免疫系統時鐘竄改、手動調整或校時跳躍的影響，確保「每 1 分鐘」就是精準的 60 秒物理時間。
  - **智慧誤差閾值模式 (Threshold-based Sync)**：支援設定誤差閾值（預設 60 秒 / 1 分鐘），僅在系統時間與 NTP 伺服器時間誤差超過此閾值時才進行寫入更新；若誤差小於閾值則略過寫入，減少時鐘跳動。
- **原生 EXE 啟動器架構**：
  - 由於 Python 3.14 (rc3) 尚未被 PyInstaller bootloader 完全相容（會產生 embedded PKG archive 讀取錯誤），我們直接使用 Windows 系統內建的 .NET 編譯器 (`csc.exe`)，將 `launcher.cs` 編譯成標準原生 Windows PE 執行檔 `WindowsTimeAutoUpdate.exe`。
  - **特色**：內建應用程式專屬圖示 `app_icon.ico`、自動調用 `pythonw.exe` 靜默執行、自動要求 UAC 管理員權限、零依賴、體積僅 7KB，雙擊秒開無黑框。
  - 支援 `create_desktop_shortcut.bat` 一鍵建立桌面快捷方式圖示。
- **系統托盤**：使用 `pystray` + `Pillow` 實作最小化至右下角系統匣常駐運行，避免干擾日常工作，提供右鍵快捷選單與 Windows 桌面通知。
- **開機自動啟動**：透過 Windows 註冊表 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` 管理開機自動以 `--minimized` 靜默常駐至系統匣。
- **單一執行個體限制**：使用 Windows Named Mutex (`CreateMutexW`) 確保背景不會多開衝突。
- **設定持久化**：`config.json` 記錄更新頻率、NTP 伺服器清單、自訂伺服器、開機自動啟動狀態等。

## 模組檔案清單
- `main.py`: 主程式進入點、命令列參數解析、Mutex 檢查
- `gui.py`: 現代科技深色卡片式儀表板介面
- `ntp_client.py`: NTP/SNTP 通訊協定與延遲計算
- `time_syncer.py`: Win32 API 系統時鐘寫入與 UAC 提權
- `scheduler.py`: 背景排程器與倒數計時
- `config_manager.py`: 設定檔讀寫
- `autostart.py`: Windows 註冊表開機啟動
- `tray_icon.py`: 系統匣圖示與右鍵選單
- `run.bat` / `run_admin.bat`: 一鍵啟動腳本 (純 ASCII 防止 cmd 編碼錯亂)
- `build.py` / `build_exe.bat`: PyInstaller 打包獨立 EXE 腳本 (Python 驅動避免 Windows cmd UTF-8 亂碼截斷)
- `test_suite.py`: 單元與功能測試套件
