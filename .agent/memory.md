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
  - 由於 Python 3.14 (rc3) 尚未被 PyInstaller bootloader 完全相容，直接使用 Windows 系統內建的 .NET 編譯器 (`csc.exe`)，將 `launcher.cs` 編譯成標準原生 Windows PE 執行檔 `WindowsTimeAutoUpdate.exe`。
  - **特色**：內建專屬圖示 `app_icon.ico`、自動調用 `pythonw.exe` 靜默執行、自動要求 UAC 管理員權限、零依賴、體積僅 16KB，雙擊秒開無黑框。
  - **開機背景啟動策略**：在 `--minimized` 模式下不主動強制彈 UAC，避免被 Windows 開機機制靜默阻擋，確保順利進入常駐。
  - **Google Drive 掛載等待容錯 (Drive-Ready Waiter)**：針對專案放置於 Google 雲端硬碟 (`G:\`) 等虛擬磁碟機，啟動器在開機 `--minimized` 模式下內建 60 秒重試循環，自動等待磁碟掛載就緒。
  - 支援 `create_desktop_shortcut.bat` 一鍵建立桌面快捷方式圖示 (採 100% 純 ASCII + Base64 UTF-8 解碼，徹底杜絕 Windows cmd.exe 多位元組中文字元指標錯位與截斷報錯)。
- **開機自動啟動架構 (LocalAppData 本機部署 + 工作排程器免 UAC 雙軌制)**：
  - **本機 LocalAppData 永久部署**：啟用開機啟動時，自動將程式核心檔案同步安裝至 `%LOCALAPPDATA%\WindowsTimeAutoUpdate\` (C 槽純 ASCII 路徑)。開機瞬間 100% 存在、秒載入，徹底解決 Google Drive (G:) 開機尚未掛載以及中文路徑編碼損壞的根本問題。
  - **Windows 工作排程器 (首選模式)**：使用 `schtasks` 註冊 `WindowsTimeAutoUpdate_Startup`，設定登入觸發 (`/sc ONLOGON`) 與最高管理員權限 (`/rl HIGHEST`)，開機免 UAC 靜默常駐。
  - **純 ASCII 批次檔**：`setup_autostart.bat` 採 100% 純 ASCII 指令，杜絕 Windows cmd.exe 多位元組中文字元斷詞亂碼截斷報錯。
- **免安裝綠色便攜架構 (零依賴 Portable Runtime)**：
  - **精簡 Runtime 目錄 (`runtime/`)**：從官方環境提取核心直譯器、標準庫、Tkinter (tcl/tk)、Pillow 與 pystray (含 six.py)，體積僅約 60MB (壓縮後僅 21MB)，完全免除目標電腦安裝 Python 之需求。
  - **原生 C# 啟動器升級 (`launcher.cs` -> `WindowsTimeAutoUpdate.exe`)**：`FindPythonw()` 優先尋找程式所在目錄之 `runtime\pythonw.exe`，免裝 Python 亦可毫秒級雙擊秒開，且完全免疫防毒軟體加殼誤判。
  - **LocalAppData 開機自啟動同步支援**：`autostart.py` 於部署至 `%LOCALAPPDATA%\WindowsTimeAutoUpdate\` 時，自動偵測並同步部署 `runtime/`，確保無 Python 電腦於開機自動啟動時依然順暢常駐。
  - **一鍵建置發行腳本**：`create_portable_package.py` 與 `build_portable_zip.bat`，可自動自我驗證依賴並輸出 `WindowsTimeAutoUpdate_Portable.zip`。
- **版本控制規範 (`.gitignore`)**：建立標準 `.gitignore` 排除 `runtime/`、`*.zip`、`build/`、`dist/` 與 `__pycache__/`，確保二進位執行時與發行壓縮包不污染 Git 倉庫，維持倉庫極簡與高效同步。
- **單一執行個體限制**：使用 Windows Named Mutex (`CreateMutexW`) 確保背景不會多開衝突。
- **設定持久化**：`config.json` 記錄更新頻率、NTP 伺服器清單、自訂伺服器、開機自動啟動狀態等。

- **HTTPS (TCP 443) 雙軌備援校時架構**：
  - **背景與問題**：在嚴格企業網管或防火牆封鎖對外 UDP Port 123 (NTP) 時，標準 NTP 會連線逾時。
  - **解決方案**：新增 `http_time_client.py`，向各大雲端服務（Google、Cloudflare、Microsoft、Apple 等）發送標準 HTTPS HEAD 請求，解析 HTTP `Date` 標頭並結合網路延遲（RTT / 2）補償進行校時。
  - **特點**：純 Python 內建標準庫（`http.client`、`ssl`、`email.utils`），零第三方相依；優先嘗試微秒級 NTP，被擋時自動無縫降級切換至 HTTPS 備援；GUI 儀表板清楚顯示當前協定與通道狀態。

## 模組檔案清單
- `.gitignore`: Git 忽略清單 (排除 runtime、zip、快取與建置暫存)
- `main.py`: 主程式進入點、命令列參數解析、Mutex 檢查
- `gui.py`: 現代科技深色卡片式儀表板介面 (含通訊協定狀態條、HTTPS 備援切換與自訂伺服器刪除按鈕)
- `ntp_client.py`: NTP/SNTP 通訊協定與延遲計算
- `http_time_client.py`: HTTPS (TCP 443) 備援時間同步客戶端與延遲補償
- `time_syncer.py`: Win32 API 系統時鐘寫入、UAC 提權與雙軌自動降級管理
- `scheduler.py`: 背景排程器與倒數計時 (支援 HTTPS 備援設定傳遞)
- `config_manager.py`: 設定檔讀寫 (含 HTTPS 備援開關與伺服器清單)
- `autostart.py`: LocalAppData 本機部署與工作排程器/登錄檔雙軌開機自啟動管理 (含 runtime 與 http_time_client 同步)
- `setup_autostart.bat`: 100% 純 ASCII 一鍵部署與註冊開機工作排程腳本
- `tray_icon.py`: 系統匣圖示與右鍵選單
- `runtime/`: 獨立免安裝精簡 Python 3.14 執行時環境 (零相依發行關鍵)
- `WindowsTimeAutoUpdate_Portable.zip`: 完整免安裝綠色便攜發行包 (約 21MB)
- `create_portable_package.py` / `build_portable_zip.bat`: 免安裝便攜包建置與自動驗證腳本
- `build_exe.bat` / `launcher.cs`: 原生 C# EXE 啟動器編譯與原始碼 (優先調用 runtime)
- `test_suite.py`: 單元與功能測試套件 (含 NTP、HTTPS 與雙軌降級測試)
- `Daily_Report_0c4e561.txt`: Commit `0c4e561` 對應之 3 天工作日誌文字檔

## 工作報表產出紀錄與決策
- **目標 Commit**：`0c4e561ad0b96c249cd8427a06a908f2f90bb8fb`
- **關鍵提示詞**：「0c4e561ad0b96c249cd8427a06a908f2f90bb8fb產生2天工作日誌」、「你覺得應該可以寫成幾天的工作日誌」、「改成3天 並存成文字檔」
- **異動評估決策**：
  - 統計指標為 8 個實質變更檔案、354 行異動代碼，落於中型架構演進級距（建議 2 ~ 3 天）。
  - 使用者原需求 2 天，經分析評估後確認擴展為 3 天可更充分體現「核心執行時提取」、「第三方模組隔離驗證」與「啟動器/排程發行對接」三個深層工程階段。
  - 符合民國年降冪排列（115.09.17、115.09.16、115.09.15）、非週一每日 3 項、純文字輸出無 Markdown 標籤之格式規範。
