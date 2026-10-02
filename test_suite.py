"""
全面單元與功能測試套件 (test_suite.py)
驗證 NTP 客戶端、排程器、設定檔、時間同步器、開機啟動與托盤模組的正確性。
"""

import os
import sys
import time
import unittest
from datetime import datetime, timezone

from autostart import get_launch_command
from config_manager import ConfigManager
from ntp_client import NTPClient, _ntp_to_system_timestamp, _system_to_ntp_timestamp
from scheduler import TimeSyncScheduler
from time_syncer import SYSTEMTIME, TimeSyncer, is_admin
from tray_icon import create_default_icon_image


class TestNTPClient(unittest.TestCase):
    """NTP 客戶端測試"""

    def test_timestamp_conversion(self):
        now = 1700000000.123456
        sec, frac = _system_to_ntp_timestamp(now)
        recovered = _ntp_to_system_timestamp(sec, frac)
        self.assertAlmostEqual(now, recovered, places=5)

    def test_query_google_ntp(self):
        client = NTPClient(timeout=4.0)
        res = client.query("time.google.com")
        self.assertTrue(res["success"], f"NTP 查詢失敗: {res.get('error')}")
        self.assertIsNotNone(res["delay_ms"])
        self.assertIsNotNone(res["offset_ms"])
        self.assertIsInstance(res["corrected_utc_dt"], datetime)
        self.assertGreater(res["delay_ms"], 0)

    def test_fallback_query(self):
        client = NTPClient(timeout=2.0)
        # 第一個是不存在的伺服器，第二個是真實伺服器
        servers = ["invalid.nonexistent.ntp.server.xyz", "time.google.com"]
        res = client.query_with_fallback(servers)
        self.assertTrue(res["success"])
        self.assertEqual(res["server"], "time.google.com")


class TestHTTPTimeClient(unittest.TestCase):
    """HTTPS (TCP 443) 備援時間客戶端測試"""

    def test_query_google_https(self):
        from http_time_client import HTTPTimeClient

        client = HTTPTimeClient(timeout=4.0)
        res = client.query("www.google.com")
        self.assertTrue(res["success"], f"HTTPS 查詢失敗: {res.get('error')}")
        self.assertEqual(res["protocol"], "HTTPS")
        self.assertIsNotNone(res["delay_ms"])
        self.assertIsNotNone(res["offset_ms"])
        self.assertIsInstance(res["corrected_utc_dt"], datetime)
        self.assertGreater(res["delay_ms"], 0)

    def test_fallback_query_https(self):
        from http_time_client import HTTPTimeClient

        client = HTTPTimeClient(timeout=2.0)
        servers = ["invalid.nonexistent.domain.xyz", "www.google.com"]
        res = client.query_with_fallback(servers)
        self.assertTrue(res["success"])
        self.assertEqual(res["protocol"], "HTTPS")
        self.assertEqual(res["server"], "www.google.com")


class TestDualProtocolFallback(unittest.TestCase):
    """NTP 與 HTTPS 雙軌自動降級備援測試"""

    def test_auto_fallback_to_https_when_ntp_fails(self):
        """當 NTP 伺服器不可達 (模擬 UDP 123 被擋) 時，自動降級切換至 HTTPS 備援"""
        syncer = TimeSyncer(timeout=2.0)
        # 給定一個保證無法連線的 NTP 伺服器
        res = syncer.sync_time(
            "192.0.2.1",  # RFC 5737 TEST-NET-1 (不可達)
            threshold_seconds=100000.0,  # 設大閾值以驗證略過寫入前之時間取得
            enable_http_fallback=True,
            http_servers=["www.google.com"],
        )
        self.assertTrue(res["success"], f"備援同步失敗: {res.get('error')}")
        self.assertEqual(res["protocol"], "HTTPS")
        self.assertTrue(res["is_fallback"])
        self.assertIn("HTTPS", res["message"])

    def test_no_fallback_when_disabled(self):
        """當停用 HTTPS 備援時，NTP 失敗應直接回傳失敗"""
        syncer = TimeSyncer(timeout=1.0)
        res = syncer.sync_time(
            "192.0.2.1",
            enable_http_fallback=False,
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["protocol"], "NTP")
        self.assertFalse(res["is_fallback"])


class TestConfigManager(unittest.TestCase):
    """設定檔管理器測試"""

    def setUp(self):
        self.test_cfg_path = "test_config_temp.json"
        if os.path.exists(self.test_cfg_path):
            os.remove(self.test_cfg_path)
        self.cm = ConfigManager(config_path=self.test_cfg_path)

    def tearDown(self):
        if os.path.exists(self.test_cfg_path):
            os.remove(self.test_cfg_path)

    def test_config_defaults_and_save(self):
        self.assertEqual(self.cm.get("interval_value"), 30)
        self.assertEqual(self.cm.get("interval_unit"), "minutes")

        self.cm.set("interval_value", 45)
        self.cm.set("interval_unit", "hours")

        # 重新載入驗證
        cm2 = ConfigManager(config_path=self.test_cfg_path)
        self.assertEqual(cm2.get("interval_value"), 45)
        self.assertEqual(cm2.get("interval_unit"), "hours")

    def test_custom_server_management(self):
        initial_count = len(self.cm.get_all_servers())
        ok = self.cm.add_custom_server("custom.ntp.test", name="測試伺服器")
        self.assertTrue(ok)
        self.assertEqual(len(self.cm.get_all_servers()), initial_count + 1)

        # 重複新增應回傳 False
        ok_dup = self.cm.add_custom_server("custom.ntp.test")
        self.assertFalse(ok_dup)

        # 刪除測試
        del_ok = self.cm.remove_custom_server("custom.ntp.test")
        self.assertTrue(del_ok)
        self.assertEqual(len(self.cm.get_all_servers()), initial_count)


class TestScheduler(unittest.TestCase):
    """背景排程器測試"""

    def test_interval_calculation(self):
        syncer = TimeSyncer()
        s = TimeSyncScheduler(syncer, interval_value=10, interval_unit="minutes")
        self.assertEqual(s.interval_seconds, 600)

        s.update_interval(2, "hours")
        self.assertEqual(s.interval_seconds, 7200)

        s.update_interval(3, "days")
        self.assertEqual(s.interval_seconds, 259200)

        s.update_interval(15, "seconds")
        self.assertEqual(s.interval_seconds, 15)

    def test_countdown_formatting(self):
        syncer = TimeSyncer()
        s = TimeSyncScheduler(syncer, interval_value=5, interval_unit="minutes")
        s.start()
        rem_str = s.get_remaining_formatted()
        self.assertIn(":", rem_str)
        s.stop()


class TestThresholdSync(unittest.TestCase):
    """智慧誤差閾值校時測試"""

    def test_threshold_sync_skipped_when_accurate(self):
        """測試當系統時鐘偏差小於設定閾值時，應跳過寫入 (skipped=True)"""
        syncer = TimeSyncer()
        # 設定極大閾值 (100000 秒)，確保大於當前任何偏差值以驗證略過邏輯
        res = syncer.sync_time("time.google.com", threshold_seconds=100000.0)
        self.assertTrue(res["success"])
        self.assertTrue(res["skipped"])
        self.assertIn("小於設定閾值", res["message"])
        self.assertEqual(res["threshold_sec"], 100000.0)

    def test_threshold_sync_not_skipped_when_exceeded(self):
        """測試當閾值為 0.0000001 秒 (極小) 時，應判定為超過閾值 (skipped=False)"""
        syncer = TimeSyncer()
        res = syncer.sync_time("time.google.com", threshold_seconds=0.0000001)
        self.assertIn("success", res)
        # 不論是否因為非管理員報錯，skipped 必須為 False
        self.assertFalse(res.get("skipped", True))

    def test_scheduler_monotonic_countdown(self):
        """測試排程器倒數計時使用單調時鐘，保證倒數秒數精準且不受 Wall-Clock 影響"""
        syncer = TimeSyncer()
        s = TimeSyncScheduler(syncer, interval_value=60, interval_unit="seconds")
        s.start()
        rem1 = s.get_remaining_seconds()
        self.assertGreater(rem1, 58.0)
        self.assertLessEqual(rem1, 60.0)
        time.sleep(0.5)
        rem2 = s.get_remaining_seconds()
        self.assertLess(rem2, rem1)
        s.stop()


class TestSystemTimeAndAutostart(unittest.TestCase):
    """系統時間與開機啟動模組測試"""

    def test_autostart_command_generation(self):
        from autostart import check_autostart_status, get_launch_command
        cmd = get_launch_command(start_minimized=True)
        self.assertTrue("WindowsTimeAutoUpdate.exe" in cmd or "main.py" in cmd)
        self.assertIn("--minimized", cmd)

        status = check_autostart_status()
        self.assertIn("enabled", status)
        self.assertIn("target_executable", status)

    def test_tray_icon_image(self):
        img = create_default_icon_image(64, 64)
        self.assertEqual(img.size, (64, 64))
        self.assertEqual(img.mode, "RGBA")


class TestLogFilter(unittest.TestCase):
    """日誌篩選與搜尋功能測試"""

    def setUp(self):
        import tkinter as tk
        from gui import ModernTimeSyncGUI
        self.root = tk.Tk()
        self.root.withdraw()
        # 建立簡化模擬物件以測試日誌篩選
        self.dummy_gui = ModernTimeSyncGUI.__new__(ModernTimeSyncGUI)
        self.dummy_gui.log_entries = []
        self.dummy_gui.var_log_filter_level = tk.StringVar(value="全部種類")
        self.dummy_gui.var_log_search = tk.StringVar(value="")
        self.dummy_gui.var_log_count = tk.StringVar(value="顯示: 0 / 0 筆")

    def tearDown(self):
        self.root.destroy()

    def test_filter_all_types(self):
        """測試全部種類篩選應匹配所有訊息"""
        from gui import ModernTimeSyncGUI
        self.dummy_gui.var_log_filter_level.set("全部種類")
        entry_info = {"timestamp": "2026-10-02 14:00:00", "level": "info", "message": "啟動中"}
        entry_err = {"timestamp": "2026-10-02 14:00:01", "level": "error", "message": "連線失敗"}
        self.assertTrue(ModernTimeSyncGUI._matches_log_filter(self.dummy_gui, entry_info))
        self.assertTrue(ModernTimeSyncGUI._matches_log_filter(self.dummy_gui, entry_err))

    def test_filter_by_level(self):
        """測試依據成功、資訊、警告、錯誤等級進行篩選"""
        from gui import ModernTimeSyncGUI
        entry_success = {"timestamp": "2026-10-02 14:00:00", "level": "success", "message": "校時成功"}
        entry_info = {"timestamp": "2026-10-02 14:00:01", "level": "info", "message": "一般狀態"}
        entry_warn = {"timestamp": "2026-10-02 14:00:02", "level": "warning", "message": "誤差小於閾值"}
        entry_err = {"timestamp": "2026-10-02 14:00:03", "level": "error", "message": "伺服器超時"}

        # 測試僅篩選成功
        self.dummy_gui.var_log_filter_level.set("✅ 成功訊息 (Success)")
        self.assertTrue(ModernTimeSyncGUI._matches_log_filter(self.dummy_gui, entry_success))
        self.assertFalse(ModernTimeSyncGUI._matches_log_filter(self.dummy_gui, entry_info))
        self.assertFalse(ModernTimeSyncGUI._matches_log_filter(self.dummy_gui, entry_warn))
        self.assertFalse(ModernTimeSyncGUI._matches_log_filter(self.dummy_gui, entry_err))

        # 測試僅篩選錯誤
        self.dummy_gui.var_log_filter_level.set("❌ 錯誤異常 (Error)")
        self.assertTrue(ModernTimeSyncGUI._matches_log_filter(self.dummy_gui, entry_err))
        self.assertFalse(ModernTimeSyncGUI._matches_log_filter(self.dummy_gui, entry_success))

    def test_filter_by_https_category(self):
        """測試 HTTPS 備援種類篩選"""
        from gui import ModernTimeSyncGUI
        self.dummy_gui.var_log_filter_level.set("🌐 HTTPS 備援")
        entry_https = {"timestamp": "2026-10-02 14:00:00", "level": "info", "message": "切換至 HTTPS 備援校時"}
        entry_ntp = {"timestamp": "2026-10-02 14:00:01", "level": "info", "message": "標準 NTP 校時完成"}
        self.assertTrue(ModernTimeSyncGUI._matches_log_filter(self.dummy_gui, entry_https))
        self.assertFalse(ModernTimeSyncGUI._matches_log_filter(self.dummy_gui, entry_ntp))

    def test_filter_with_keyword_search(self):
        """測試關鍵字不分大小寫即時過濾"""
        from gui import ModernTimeSyncGUI
        self.dummy_gui.var_log_filter_level.set("全部種類")
        self.dummy_gui.var_log_search.set("google")
        entry1 = {"timestamp": "2026-10-02 14:00:00", "level": "info", "message": "向 time.google.com 查詢"}
        entry2 = {"timestamp": "2026-10-02 14:00:01", "level": "info", "message": "向 tock.stdtime.gov.tw 查詢"}
        self.assertTrue(ModernTimeSyncGUI._matches_log_filter(self.dummy_gui, entry1))
        self.assertFalse(ModernTimeSyncGUI._matches_log_filter(self.dummy_gui, entry2))


class TestResponsiveLayout(unittest.TestCase):
    """小螢幕自適應與響應式版面測試"""

    def setUp(self):
        import tkinter as tk
        from gui import ModernTimeSyncGUI
        self.root = tk.Tk()
        self.root.withdraw()
        self.gui = ModernTimeSyncGUI.__new__(ModernTimeSyncGUI)
        self.gui.is_settings_collapsed = False
        self.gui.is_log_maximized = False
        self.gui.var_interval_val = tk.StringVar(value="15")
        self.gui.var_unit_display = tk.StringVar(value="分鐘 (Minutes)")
        self.gui.var_selected_server = tk.StringVar(value="time.google.com")
        self.gui.var_threshold_enabled = tk.BooleanVar(value=True)
        self.gui.var_threshold_sec = tk.StringVar(value="30")
        self.gui.var_settings_summary = tk.StringVar(value="")

        # 模擬 UI 元件容器
        self.gui.settings_frame = tk.Frame(self.root)
        self.gui.btn_toggle_settings = tk.Button(self.root)
        self.gui.dashboard_card = tk.Frame(self.root)
        self.gui.settings_container = tk.Frame(self.root)
        self.gui.actions_card = tk.Frame(self.root)
        self.gui.log_card = tk.Frame(self.root)
        self.gui.btn_maximize_log = tk.Button(self.root)

        # 預先 pack 以便測試 pack_forget 與 pack
        self.gui.dashboard_card.pack()
        self.gui.settings_container.pack()
        self.gui.settings_frame.pack()
        self.gui.actions_card.pack()
        self.gui.log_card.pack()

    def tearDown(self):
        self.root.destroy()

    def test_settings_collapse_toggle(self):
        """測試設定區域之收合與展開切換"""
        from gui import ModernTimeSyncGUI
        self.assertFalse(self.gui.is_settings_collapsed)
        ModernTimeSyncGUI._toggle_settings_collapsed(self.gui)
        self.assertTrue(self.gui.is_settings_collapsed)
        self.assertEqual(self.gui.btn_toggle_settings["text"], "▼ 展開設定")

        # 再次點擊還原展開
        ModernTimeSyncGUI._toggle_settings_collapsed(self.gui)
        self.assertFalse(self.gui.is_settings_collapsed)
        self.assertEqual(self.gui.btn_toggle_settings["text"], "▲ 收合設定")

    def test_log_focus_mode_toggle(self):
        """測試日誌專注模式之全展開與還原切換"""
        from gui import ModernTimeSyncGUI
        self.assertFalse(self.gui.is_log_maximized)
        ModernTimeSyncGUI._toggle_log_focus_mode(self.gui)
        self.assertTrue(self.gui.is_log_maximized)
        self.assertEqual(self.gui.btn_maximize_log["text"], "🗗 還原視圖")

        # 再次點擊還原
        ModernTimeSyncGUI._toggle_log_focus_mode(self.gui)
        self.assertFalse(self.gui.is_log_maximized)
        self.assertEqual(self.gui.btn_maximize_log["text"], "⛶ 展開視圖")

    def test_settings_summary_generation(self):
        """測試收合狀態之設定摘要字串產生"""
        from gui import ModernTimeSyncGUI
        ModernTimeSyncGUI._update_settings_summary(self.gui)
        summary = self.gui.var_settings_summary.get()
        self.assertIn("15 分鐘", summary)
        self.assertIn("time.google.com", summary)
        self.assertIn("30s", summary)


if __name__ == "__main__":
    unittest.main(verbosity=2)



