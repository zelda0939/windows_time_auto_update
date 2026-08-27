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
        """測試當系統時鐘偏差小於 60 秒時，應跳過寫入 (skipped=True)"""
        syncer = TimeSyncer()
        # 設定閾值為 60 秒 (目前電腦時鐘與 Google NTP 誤差通常只有幾毫秒到幾秒，遠小於 60 秒)
        res = syncer.sync_time("time.google.com", threshold_seconds=60.0)
        self.assertTrue(res["success"])
        self.assertTrue(res["skipped"])
        self.assertIn("小於設定閾值", res["message"])
        self.assertEqual(res["threshold_sec"], 60.0)

    def test_threshold_sync_not_skipped_when_exceeded(self):
        """測試當閾值為 0.0000001 秒 (極小) 時，應判定為超過閾值 (skipped=False)"""
        syncer = TimeSyncer()
        res = syncer.sync_time("time.google.com", threshold_seconds=0.0000001)
        self.assertIn("success", res)
        # 不論是否因為非管理員報錯，skipped 必須為 False
        self.assertFalse(res.get("skipped", True))


class TestSystemTimeAndAutostart(unittest.TestCase):
    """系統時間與開機啟動模組測試"""

    def test_autostart_command_generation(self):
        cmd = get_launch_command(start_minimized=True)
        self.assertIn("main.py", cmd)
        self.assertIn("--minimized", cmd)

    def test_tray_icon_image(self):
        img = create_default_icon_image(64, 64)
        self.assertEqual(img.size, (64, 64))
        self.assertEqual(img.mode, "RGBA")


if __name__ == "__main__":
    unittest.main(verbosity=2)
