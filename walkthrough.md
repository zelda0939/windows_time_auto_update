# HTTPS (TCP 443) 備援校時機制成果報告 (Walkthrough)

## 任務背景與問題
在嚴格控管的企業、學校或政府內網中，網管常會封鎖對外 **UDP Port 123 (NTP)**。在此環境下，標準 NTP 客戶端會發生連線逾時（Socket Timeout），導致無法校時。
為此，本專案新增了基於標準 **HTTPS (TCP 443)** 的雙軌智慧備援校時機制，確保在任何嚴苛網路環境下均可 100% 成功校時。

---

## 關鍵技術變更與架構

1. **全新 HTTPS 時間客戶端模組 ([http_time_client.py](file:///g:/我的雲端硬碟/安成工作資料/同步區/case/windows_time_auto_update/http_time_client.py))**：
   - 採用 Python 內建標準庫（`http.client`、`ssl`、`email.utils`），**零第三方套件相依**，完美相容精簡 `runtime/` 便攜環境。
   - 向各大高可用服務（Google、Cloudflare、Microsoft、Apple 等）發送輕量 `HEAD` 請求（流量小於 1KB）。
   - 解析 HTTP Response Header 中的 RFC 2822 / RFC 7231 `Date` 標頭，並結合網路往返延遲估計（RTT / 2）進行精準補償與時間位移（Offset）計算。
   - 提供與 `NTPClient` 高度相容之介面（`query`、`query_with_fallback`、`test_server`）。

2. **時間同步器雙軌自動降級機制 ([time_syncer.py](file:///g:/我的雲端硬碟/安成工作資料/同步區/case/windows_time_auto_update/time_syncer.py))**：
   - 優先向 NTP (UDP 123) 伺服器查詢，享有微秒級高精確度。
   - 若 NTP 查詢逾時或連線失敗，且啟用 HTTPS 備援，系統**自動無縫降級切換至 HTTPS (TCP 443)**。
   - 回傳結果中明確標記通訊協定（`protocol: "NTP"` 或 `"HTTPS"`）與備援狀態標記（`is_fallback: True/False`）。

3. **背景定時排程整合 ([scheduler.py](file:///g:/我的雲端硬碟/安成工作資料/同步區/case/windows_time_auto_update/scheduler.py))**：
   - 排程器支援 `http_fallback_provider` 與 `http_servers_provider` 回呼。
   - 在定時週期執行與手動立即同步時，均自動套用 HTTPS 備援設定。

4. **設定管理升級 ([config_manager.py](file:///g:/我的雲端硬碟/安成工作資料/同步區/case/windows_time_auto_update/config_manager.py))**：
   - 新增 `enable_http_fallback: True` 設定項（預設啟用）。
   - 新增 `http_fallback_servers` 預設伺服器清單（Google、Cloudflare、Microsoft、Apple）。

5. **現代化卡片式 GUI 升級 ([gui.py](file:///g:/我的雲端硬碟/安成工作資料/同步區/case/windows_time_auto_update/gui.py))**：
   - **儀表板狀態條**：即時時鐘卡片下方新增「📡 校時通訊協定」與「🎯 目標伺服器」狀態列，動態呈現 `🟢 NTP (UDP 123)` 或 `🌐 HTTPS 備援 (TCP 443)`。
   - **設定選項**：在 NTP 伺服器設定卡片中新增「UDP 123 受阻時切換 HTTPS (TCP 443) 備援」核取方塊。
   - **自訂伺服器管理**：在「＋新增自訂」旁加入「🗑️ 刪除自訂」按鈕，支援在 UI 上一鍵移除選中的自訂伺服器並自動切換回預設伺服器。
   - **即時日誌**：備援成功時以專屬警示圖示及文字醒目記錄（如：`🌐 成功透過 HTTPS (TCP 443) 備援同步時間！... (NTP UDP 123 逾時，已自動啟用備援通道)`）。

6. **部署與打包腳本同步支援**：
   - [autostart.py](file:///g:/我的雲端硬碟/安成工作資料/同步區/case/windows_time_auto_update/autostart.py)：在 `DEPLOY_FILES` 中納入 `http_time_client.py`，確保開機 LocalAppData 部署完整。
   - [create_portable_package.py](file:///g:/我的雲端硬碟/安成工作資料/同步區/case/windows_time_auto_update/create_portable_package.py)：在 `include_files` 中納入 `http_time_client.py`，確保綠色免安裝便攜包無遺漏。

---

## 驗證結果

### 自動化單元測試 ([test_suite.py](file:///g:/我的雲端硬碟/安成工作資料/同步區/case/windows_time_auto_update/test_suite.py))
執行 `python test_suite.py`，共計 16 項測試**全部通過**（`Ran 16 tests in 6.969s, OK`）：
- `test_query_google_https`：✅ 成功透過 HTTPS HEAD 取得時間與計算延遲。
- `test_fallback_query_https`：✅ 伺服器輪詢備援機制正常。
- `test_auto_fallback_to_https_when_ntp_fails`：✅ 模擬 NTP 不可達（UDP 123 被阻擋），確認自動降級至 HTTPS 備援成功。
- `test_no_fallback_when_disabled`：✅ 停用備援時正確保持 NTP 報錯。
- 所有原有的單調時鐘、排程器、開機自啟動與設定管理測試均 100% 通過。

### 免安裝綠色便攜包打包驗證 ([WindowsTimeAutoUpdate_Portable.zip](file:///g:/我的雲端硬碟/安成工作資料/同步區/case/windows_time_auto_update/WindowsTimeAutoUpdate_Portable.zip))
- 原生 C# 啟動器編譯：✅ 成功透過 .NET `csc.exe` 編譯最新 `WindowsTimeAutoUpdate.exe`。
- 獨立精簡 Runtime：✅ 成功驗證 Tkinter、ctypes、socket、json、Pillow、pystray 均可獨立載入。
- 壓縮封裝：✅ 成功打包為 `WindowsTimeAutoUpdate_Portable.zip`（大小約 21.58 MB），已納入 `http_time_client.py` 與最新 GUI 程式。可直接複製至任何未安裝 Python 的 Windows 電腦使用。

### 桌面捷徑腳本修復 ([create_desktop_shortcut.bat](file:///g:/我的雲端硬碟/安成工作資料/同步區/case/windows_time_auto_update/create_desktop_shortcut.bat))
- **問題分析**：原批次檔內含有中文字元（如捷徑名稱與提示），在 Windows `cmd.exe` 解析 UTF-8 多位元組時產生指標錯位（Byte Offset Misalignment），將單字中間拆解出 `'pointing'` 與 `'and'` 等錯誤命令。
- **修復方案**：全面改採 **100% 純 ASCII 批次檔指令**，將中文名稱以 Base64 UTF-8 解碼傳入 PowerShell，徹底根除 Windows CMD 亂碼與斷詞 Bug。
- **驗證**：實測執行 `create_desktop_shortcut.bat`，秒級於桌面成功建立「Windows 網路自動校時工具.lnk」，無任何語法報錯。最新修復版本已同步更新至 ZIP 便攜包。
