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

- **日誌特定種類篩選與即時搜尋架構 (Log Category Filter & Live Search)**：
  - **結構化日誌歷史**：在 GUI 中維護 `log_entries` 串列，保存 `timestamp`、`level`（`info`、`success`、`warning`、`error`）與 `message`，上限 2000 筆。
  - **特定種類篩選下拉選單**：支援「全部種類」、「✅ 成功訊息 (Success)」、「ℹ️ 一般資訊 (Info)」、「⚠️ 警告提示 (Warning)」、「❌ 錯誤異常 (Error)」、「🌐 HTTPS 備援」與「⏰ 校時紀錄」。
  - **即時全文搜尋與計數**：支援不分大小寫關鍵字過濾、一鍵清除按鈕（`✕`）以及「顯示: X / Y 筆」動態計數。
  - **效能最佳化**：新日誌進入時採「符合即追加 (Append-on-match)」模式，僅在篩選條件改變時執行重繪，杜絕介面閃爍。
  - **日誌文字檔匯出**：提供「💾 匯出日誌」按鈕，支援將當前篩選之日誌儲存為 UTF-8 文字或日誌檔。

## 模組檔案清單
- `.gitignore`: Git 忽略清單 (排除 runtime、zip、快取與建置暫存)
- `main.py`: 主程式進入點、命令列參數解析、Mutex 檢查
- `gui.py`: 現代科技深色卡片式儀表板介面 (含通訊協定狀態條、HTTPS 備援切換、日誌特定種類篩選工具列、即時搜尋與匯出功能)
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
- `Daily_Report_ad7b4cb.txt`: Commit `ad7b4cb` 對應之 4 天工作日誌文字檔

## 工作報表產出紀錄與決策
### 紀錄 1：Commit `0c4e561ad0b96c249cd8427a06a908f2f90bb8fb`
- **關鍵提示詞**：「0c4e561ad0b96c249cd8427a06a908f2f90bb8fb產生2天工作日誌」、「你覺得應該可以寫成幾天的工作日誌」、「改成3天 並存成文字檔」
- **異動評估決策**：
  - 統計指標為 8 個實質變更檔案、354 行異動代碼，落於中型架構演進級距（建議 2 ~ 3 天）。
  - 使用者原需求 2 天，經分析評估後確認擴展為 3 天可更充分體現「核心執行時提取」、「第三方模組隔離驗證」與「啟動器/排程發行對接」三個深層工程階段。
  - 符合民國年降冪排列（115.09.17、115.09.16、115.09.15）、非週一每日 3 項、純文字輸出無 Markdown 標籤之格式規範。

### 紀錄 2：Commit `ad7b4cbc2307474899d1502718c5f8f807213930`
- **關鍵提示詞**：「ad7b4cbc2307474899d1502718c5f8f807213930可以寫成幾天的工作日誌?」、「4天 寫成文字檔」、「前面改成 Windows校時工具」
- **異動評估決策**：
  - 統計指標為 15 個變更檔案、713 行異動代碼，落於中大型功能演進級距（標準推薦 4 ~ 5 天）。
  - 使用者指定採用 4 天，專案前綴簡化為「Windows校時工具」。
  - 排程由 Commit 日期往回推算平日：115.09.22（二）、115.09.21（一）、115.09.18（五）、115.09.17（四），排除週末。
  - 115.09.21（週一）完全符合前兩項固定「公司早會」、「例行資料備份檢查」且全日 4 項之特殊規範；其餘天數每日 3 項。
  - 成功輸出純文字檔 `Daily_Report_ad7b4cb.txt`，無任何 Markdown 標籤。

### 紀錄 3：日誌特定種類訊息篩選與即時搜尋功能
- **關鍵提示詞**：「log讓我可以篩選特定種類的訊息」
- **異動評估決策**：
  - **核心痛點**：舊版日誌終端僅直接將文字追加進 Text Widget，無結構化歷史儲存，無法回溯過濾特定事件（如成功、錯誤或警告）。
  - **技術架構決策**：
    - 導入 `log_entries` 記憶體歷史串列（上限 2000 筆），兼顧查詢與效能防溢。
    - 在卡片頂部加入專屬控制工具列，整合「種類下拉選單」、「即時關鍵字搜尋框」、「一鍵清除」、「即時筆數統計」、「匯出文字檔」與「清空記錄」。
    - 採高效「Append-on-match」追加策略，杜絕常規日誌刷新時的畫面閃爍與不必要重繪。
    - 擴充 `test_suite.py` 新增 4 項專屬測試（全種類、特定等級、HTTPS 分類、不分大小寫關鍵字），20 項測試全部順利通過。

### 紀錄 4：小螢幕日誌顯示空間優化 (版面緊湊化 + 設定收合 + 日誌專注模式)
- **關鍵提示詞**：「log的顯示區域在小螢幕的畫面上會被壓縮到幾乎看不到幾行log 想看看有沒有優化辦法」
- **異動評估決策**：
  - **核心痛點**：小螢幕筆電（如 768p）或 125%/150% 縮放環境下垂直可用高度僅約 600~650px，上方儀表板、排程設定、NTP 設定與選項累積近 570px 固定高度，將底部日誌壓縮至僅剩 1~2 行。
  - **解決方案與技術架構**：
    - **全域邊距緊湊化**：收斂垂直 padding/margin，動態依螢幕高度限制預設高度（<=800px 時自動降至 `screen_h - 70`），最小限制下調至 `740x480`，常規狀態下直接多騰出 70~90px（多看 5~7 行）。
    - **中間設定卡片一鍵折疊/展開 (`_toggle_settings_collapsed`)**：排程與伺服器通常僅初次設定，收合後可騰出 ~210px 空間，並在收合條動態呈現設定摘要 `(每 X 分鐘 | 伺服器 | 閾值)`。
    - **日誌專注模式 / 一鍵展開最大化 (`_toggle_log_focus_mode`)**：日誌工具列新增「⛶ 展開視圖」/「🗗 還原視圖」按鈕，點擊時一鍵隱藏上方儀表板與設定，讓日誌終端佔據視窗 90% 以上空間（一次可看 35~45 行）。
    - 擴充 `test_suite.py` 新增 3 項響應式單元測試，23 項測試全部通過。

### 紀錄 5：免安裝綠色便攜發行包重新建置與打包
- **關鍵提示詞**：「重新打包便攜版」
- **異動評估決策**：
  - **建置流程**：
    1. 調用 .NET `csc.exe` 重新編譯原生 C# 啟動器 `WindowsTimeAutoUpdate.exe`。
    2. 調用 `create_portable_package.py` 提取 Python 3.14 獨立精簡 Runtime。
    3. 通過環境隔離自主驗證（tkinter, ctypes, socket, json, PIL, pystray 全部正常載入）。
    4. 完整納入最新日誌種類篩選、即時搜尋、自適應緊湊版面、設定收合與日誌展開視圖之 `gui.py` 及全套模組。
    5. 產出 `WindowsTimeAutoUpdate_Portable.zip`（21.58 MB），達成目標電腦零相依開箱即用。

### 紀錄 6：手動一鍵重新打包批次檔建置
- **關鍵提示詞**：「能寫bat讓我可以手動點擊就可以重新打包便攜版嗎?」
- **異動評估決策**：
  - **核心痛點**：舊有 `build_portable_zip.bat` 缺少 `cd /d "%~dp0"`，在以管理員權限執行時工作目錄會跳至 `System32` 導致路徑錯誤。
  - **技術架構決策**：新建 `一鍵重新打包便攜版.bat`，同步升級 `build_portable_zip.bat`。

### 紀錄 7：批次檔 UTF-8 多位元組截斷錯位與 Explorer 相對路徑問題修復
- **關鍵提示詞**：「我點了 一鍵重新打包便攜版.bat 他就閃了一下然後就跳出 本機的目錄而已」
- **異動評估決策**：
  - **根本原因排查**：
    1. **Byte Offset Misalignment 錯位**：Windows `cmd.exe` 在逐行讀取含中文字元的 UTF-8 批次檔時，因字元長度指標跳轉錯位，導致指令被切割（如 `'ho.'`、`'ate.exe...'`），引發語法崩潰閃退。
    2. **Explorer 相對路徑回退**：`explorer /select` 指令若未傳入絕對路徑，Windows Shell 找不到項目時會預設 fallback 開啟「本機（This PC）」。
  - **解決方案與修復架構**：
    - 批次檔全面落實 **100% 純 ASCII 語法**（文字與提示由 Python 內部輸出），徹底根除 `cmd.exe` 換行錯位。
    - 結尾改用標準 `pause` 確實等待鍵盤輸入，並傳入 `%~dp0WindowsTimeAutoUpdate_Portable.zip` 完整絕對路徑，確保檔案總管 100% 精準高亮選中產出之壓縮包。





