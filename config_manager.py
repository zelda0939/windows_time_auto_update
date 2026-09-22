"""
設定檔管理模組 (config_manager.py)
負責讀取、儲存與維護應用程式設定檔 (config.json)
"""

import json
import os
from typing import Any, Dict, List
from ntp_client import DEFAULT_NTP_SERVERS

CONFIG_FILENAME = "config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "auto_sync": True,
    "interval_value": 30,
    "interval_unit": "minutes",  # "seconds", "minutes", "hours", "days"
    "selected_server": "tock.stdtime.gov.tw",
    "use_fallback": True,
    "custom_servers": [],
    "auto_start": False,
    "start_minimized": False,
    "minimize_to_tray": True,
    "show_notifications": True,
    "sync_on_startup": True,
    "threshold_sync_enabled": False,
    "threshold_seconds": 60,
    "enable_http_fallback": True,
    "http_fallback_servers": [
        "www.google.com",
        "www.cloudflare.com",
        "www.microsoft.com",
        "www.apple.com",
    ],
}


class ConfigManager:
    """設定檔管理器"""

    def __init__(self, config_path: str = CONFIG_FILENAME):
        # 若為相對路徑，則相對於 main 所在目錄
        if not os.path.isabs(config_path):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.config_path = os.path.join(base_dir, config_path)
        else:
            self.config_path = config_path

        self.config: Dict[str, Any] = {}
        self.load()

    def load(self) -> Dict[str, Any]:
        """從硬碟載入設定檔，若不存在則建立並寫入預設值"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                # 合併預設值 (確保新增的設定欄位不會遺漏)
                self.config = DEFAULT_CONFIG.copy()
                self.config.update(loaded)
            except Exception as e:
                print(f"讀取設定檔失敗，重設為預設值: {e}")
                self.config = DEFAULT_CONFIG.copy()
                self.save()
        else:
            self.config = DEFAULT_CONFIG.copy()
            self.save()

        return self.config

    def save(self) -> bool:
        """將當前記憶體中的設定值寫入硬碟"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"儲存設定檔失敗: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """取得特定設定鍵值"""
        return self.config.get(key, default)

    def set(self, key: str, value: Any, auto_save: bool = True):
        """設定特定設定鍵值"""
        self.config[key] = value
        if auto_save:
            self.save()

    def get_all_servers(self) -> List[Dict[str, str]]:
        """取得包含預設與自訂的所有 NTP 伺服器列表"""
        servers = list(DEFAULT_NTP_SERVERS)
        custom_list = self.get("custom_servers", [])
        for c in custom_list:
            if isinstance(c, dict) and "host" in c:
                servers.append(c)
            elif isinstance(c, str):
                servers.append({"name": f"自訂 ({c})", "host": c, "region": "使用者自訂"})
        return servers

    def add_custom_server(
        self, host: str, name: str = "", region: str = "使用者自訂"
    ) -> bool:
        """新增自訂 NTP 伺服器"""
        host = host.strip()
        if not host:
            return False

        # 檢查是否已存在
        for s in self.get_all_servers():
            if s["host"].lower() == host.lower():
                return False

        if not name:
            name = f"自訂伺服器 ({host})"

        custom_list = self.get("custom_servers", [])
        custom_list.append({"name": name, "host": host, "region": region})
        self.set("custom_servers", custom_list, auto_save=True)
        return True

    def remove_custom_server(self, host: str) -> bool:
        """移除自訂 NTP 伺服器"""
        custom_list = self.get("custom_servers", [])
        new_list = [c for c in custom_list if c.get("host", "").lower() != host.lower()]
        if len(new_list) != len(custom_list):
            self.set("custom_servers", new_list, auto_save=True)
            return True
        return False
