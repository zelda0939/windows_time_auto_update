"""
系統匣常駐與通知模組 (tray_icon.py)
透過 pystray 與 Pillow 實作 Windows 系統托盤 (System Tray) 圖示、右鍵快捷選單與氣泡通知。
"""

import threading
from typing import Callable, Optional
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item


def create_default_icon_image(width: int = 64, height: int = 64) -> Image.Image:
    """動態產生一個精緻現代的時鐘風格系統匣圖示"""
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # 繪製圓形底色 (深藍色漸層感)
    padding = 4
    draw.ellipse(
        [padding, padding, width - padding, height - padding],
        fill="#2563EB",  # 藍色 (Tailwind Blue-600)
        outline="#60A5FA",  # 淺藍邊框 (Blue-400)
        width=3,
    )

    # 繪製中心點
    cx, cy = width // 2, height // 2
    draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill="#FFFFFF")

    # 繪製時針與分針 (指向上方偏右，例如 2點整或 10點10分)
    # 分針指向上方 (12點方向)
    draw.line([cx, cy, cx, padding + 10], fill="#FFFFFF", width=3)
    # 時針指向右上方 (2點方向)
    draw.line([cx, cy, cx + 14, cy - 6], fill="#FCD34D", width=3)

    return image


class TrayIconManager:
    """系統匣圖示管理器"""

    def __init__(
        self,
        app_title: str = "Windows 自動網路校時工具",
        on_show_window: Optional[Callable[[], None]] = None,
        on_sync_now: Optional[Callable[[], None]] = None,
        on_toggle_auto_sync: Optional[Callable[[], None]] = None,
        is_auto_sync_active: Optional[Callable[[], bool]] = None,
        get_status_text: Optional[Callable[[], str]] = None,
        on_exit: Optional[Callable[[], None]] = None,
    ):
        """
        初始化系統匣管理器

        :param app_title: 托盤提示標題
        :param on_show_window: 點選顯示主視窗回呼
        :param on_sync_now: 點選立即同步回呼
        :param on_toggle_auto_sync: 點選切換自動同步回呼
        :param is_auto_sync_active: 查詢自動同步是否啟用的回呼
        :param get_status_text: 查詢目前狀態字串的回呼
        :param on_exit: 點選結束程式回呼
        """
        self.app_title = app_title
        self.on_show_window = on_show_window
        self.on_sync_now = on_sync_now
        self.on_toggle_auto_sync = on_toggle_auto_sync
        self.is_auto_sync_active = is_auto_sync_active
        self.get_status_text = get_status_text
        self.on_exit = on_exit

        self.icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None

    def _build_menu(self):
        """建立右鍵選單項目"""

        def _get_toggle_text(item_obj):
            if self.is_auto_sync_active and self.is_auto_sync_active():
                return "自動同步：[已開啟] (點擊暫停)"
            return "自動同步：[已暫停] (點擊啟用)"

        def _get_status_text(item_obj):
            if self.get_status_text:
                return f"狀態：{self.get_status_text()}"
            return "狀態：待命中"

        menu = pystray.Menu(
            item("開啟主畫面", lambda icon, item: self._handle_show_window(), default=True),
            item("立即同步時間", lambda icon, item: self._handle_sync_now()),
            item(_get_toggle_text, lambda icon, item: self._handle_toggle_auto_sync()),
            pystray.Menu.SEPARATOR,
            item(_get_status_text, lambda icon, item: None, enabled=False),
            pystray.Menu.SEPARATOR,
            item("結束程式", lambda icon, item: self._handle_exit()),
        )
        return menu

    def _handle_show_window(self):
        if self.on_show_window:
            self.on_show_window()

    def _handle_sync_now(self):
        if self.on_sync_now:
            self.on_sync_now()

    def _handle_toggle_auto_sync(self):
        if self.on_toggle_auto_sync:
            self.on_toggle_auto_sync()
        self.update_menu()

    def _handle_exit(self):
        if self.on_exit:
            self.on_exit()
        self.stop()

    def start(self):
        """在背景線程啟動系統匣圖示"""
        if self.icon is not None:
            return

        image = create_default_icon_image()
        menu = self._build_menu()

        self.icon = pystray.Icon(
            name="WindowsTimeAutoUpdate",
            icon=image,
            title=self.app_title,
            menu=menu,
        )

        def _run():
            try:
                self.icon.run()
            except Exception as e:
                print(f"系統匣執行發生錯誤: {e}")

        self._thread = threading.Thread(
            target=_run, daemon=True, name="TrayIconThread"
        )
        self._thread.start()

    def update_menu(self):
        """動態刷新右鍵選單項目狀態"""
        if self.icon:
            self.icon.menu = self._build_menu()
            self.icon.update_menu()

    def notify(self, message: str, title: Optional[str] = None):
        """發送 Windows 桌面氣泡通知"""
        if self.icon:
            try:
                self.icon.notify(
                    message,
                    title=title if title else self.app_title,
                )
            except Exception as e:
                print(f"發送系統通知失敗: {e}")

    def stop(self):
        """停止系統匣圖示"""
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
