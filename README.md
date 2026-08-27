# ⚡ Windows 網路自動校時工具 (Windows Auto Time Synchronizer)

一個輕量、穩定、高精確度且支援自訂更新頻率的 Windows 網路自動校時桌面工具。可常駐於 Windows 右下角系統匣（System Tray），定時自動與國家標準時間或全球頂級 NTP 伺服器校準電腦時鐘。

---

## ✨ 核心特色與功能

1. **⏱️ 高度自訂更新頻率與智慧閾值保護**
   - 支援自由設定定時同步間隔：每 **X 秒 / 分鐘 / 小時 / 天**。
   - 提供快速預設按鈕：[5 分鐘]、[15 分鐘]、[1 小時]、[6 小時]、[1 天]。
   - **🎯 智慧誤差閾值模式**：支援勾選「僅在時間誤差超過閾值時才進行寫入同步」（預設超過 60 秒 / 1 分鐘才同步，秒數可自由調整），當電腦時鐘準確時自動略過寫入，減少系統時鐘跳動。
   - 介面即時顯示「下次預計同步時間」與「即時倒數計時」。

2. **🌐 高精度 NTP/SNTP 核心與備援機制**
   - 實作標準 RFC 5905 NTPv4 通訊協定，精確計算網路往返延遲（Round-Trip Delay）與時間誤差（Offset）。
   - 內建優質伺服器清單：
     - **台灣國家時間與頻率標準實驗室**（`tock.stdtime.gov.tw` / `tick.stdtime.gov.tw` / `time.stdtime.gov.tw`）
     - **Google NTP** (`time.google.com`)
     - **Cloudflare NTP** (`time.cloudflare.com`)
     - **微軟官方 NTP** (`time.windows.com`)
     - **NTP Pool** (`pool.ntp.org` / `tw.pool.ntp.org`)
   - 支援 **「測試延遲 (Ping)」** 功能與 **「自訂新增 NTP 伺服器」**。
   - 支援 **自動備援容錯**：若首選伺服器無回應，自動依序輪詢備援伺服器。

3. **🛡️ 系統時間精準寫入與權限管理**
   - 透過 Windows 核心 API `kernel32.SetSystemTime` 精準寫入毫秒級 UTC 系統時間。
   - 自動偵測系統管理員權限；若權限不足，提供一鍵 UAC 提權重啟按鈕。

4. **📌 系統匣（System Tray）常駐與開機自動啟動**
   - 支援縮小至右下角通知區常駐背景運行，不佔用工作列空間。
   - 右鍵選單支援：「開啟主畫面」、「立即同步時間」、「啟用/暫停自動同步」、「狀態提示」、「結束程式」。
   - 支援一鍵設定 **開機自動啟動**（寫入 Windows 登錄檔，開機自動在背景常駐）。
   - 支援同步完成時彈出 Windows 桌面氣泡通知。

5. **📊 現代化深色儀表板 UI**
   - 科技感深色卡片式儀表板（Dark Mode），提供即時大數字時鐘與狀態指標。
   - 內建即時日誌終端（Log Console），詳細紀錄每一次校時之時間戳、伺服器、延遲與誤差。

---

## 🚀 快速開始

### 方式 1：直接執行 WindowsTimeAutoUpdate.exe（最推薦）
雙擊專案目錄下的：
```bash
WindowsTimeAutoUpdate.exe
```
*(💡 雙擊 `create_desktop_shortcut.bat`，可一鍵在桌面建立專屬時鐘圖示的快捷方式！)*

---

### 方式 2：使用腳本啟動
雙擊執行專案目錄下的：
```bash
run_admin.bat
```

---

### 方式 3：使用命令列啟動
```bash
python main.py
```
以最小化模式啟動（直接常駐至系統匣）：
```bash
python main.py --minimized
```

---

## 🛠️ 自行重新編譯 WindowsTimeAutoUpdate.exe

若需要重新編譯原生 EXE，只需雙擊：
```bash
build_exe.bat
```
腳本將自動調用 Windows 內建的 .NET 編譯器生成專屬時鐘圖示的 `WindowsTimeAutoUpdate.exe`。

---

## 📁 檔案結構說明

| 檔案名稱 | 說明 |
| :--- | :--- |
| `main.py` | 程式主要進入點、單一實例互斥鎖與生命週期管理 |
| `gui.py` | 現代化 Tkinter 儀表板視窗介面與事件控制 |
| `ntp_client.py` | RFC 5905 NTP 客戶端實作、延遲與時間偏差計算 |
| `time_syncer.py` | Windows API `SetSystemTime` 系統時鐘寫入與 UAC 權限管理 |
| `scheduler.py` | 非同步背景定時排程器與倒數計時器 |
| `config_manager.py` | `config.json` 設定檔讀寫與自訂伺服器管理 |
| `autostart.py` | Windows 開機自動啟動登錄檔管理 |
| `tray_icon.py` | 系統匣圖示 (pystray) 與右鍵選單 |
| `run.bat` / `run_admin.bat` | 一鍵啟動批次檔 |
| `build.py` / `build_exe.bat` | PyInstaller 單檔編譯打包 Python 核心與批次腳本 |
| `requirements.txt` | Python 依賴套件清單 |

---

## ❓ 常見問題 (FAQ)

### Q1: 為什麼校時會顯示「權限不足」？
> **A:** Windows 作業系統的安全規範限制只有具備「系統管理員 (Administrator)」權限的程序才能修改系統時鐘。請以系統管理員身分執行 `run_admin.bat`，或在介面頂端點擊黃色的「⚠️ 點擊以管理員權限重啟」按鈕即可。

### Q2: 關閉視窗後程式還在執行嗎？
> **A:** 預設有勾選「點擊關閉視窗 (X) 時縮小至系統匣」，因此點擊右上角 X 關閉視窗後，程式會常駐在螢幕右下角系統匣，並依照您設定的頻率繼續在背景自動校時。如欲完全結束程式，可於系統匣圖示點擊右鍵選擇「結束程式」。

### Q3: 如何設定電腦開機後自動在背景校時？
> **A:** 只要在主畫面中勾選 **「開機自動啟動 (常駐於系統匣)」**，程式會自動寫入 Windows 登錄檔，電腦每次開機時就會自動於背景啟動並常駐於系統匣，完全無需手動開啟。
