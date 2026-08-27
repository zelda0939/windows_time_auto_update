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
- **權限管理與無黑框常駐**：
  - 檢測 Administrator 權限（`IsUserAnAdmin`），未提升時支援自動以 UAC 提權執行。
  - 全面採用 `pythonw.exe` 配合 PowerShell `-WindowStyle Hidden` 啟動，徹底避免啟動時留下黑色命令提示字元 (cmd/python.exe) 視窗。
  - 加入 Windows `SetCurrentProcessExplicitAppUserModelID`，使視窗在工具列上擁有專屬名稱與圖示，不再顯示為通用的 python.exe。
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
- `run.bat` / `run_admin.bat`: 一鍵啟動腳本
- `build_exe.bat`: PyInstaller 打包獨立 EXE 腳本
- `test_suite.py`: 單元與功能測試套件
