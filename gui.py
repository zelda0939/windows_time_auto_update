"""
使用者圖形介面模組 (gui.py)
採用現代化高質感深色卡片儀表板設計 (Tkinter + ttk)
提供即時時鐘、倒數計時、頻率自訂、NTP 伺服器管理、日誌記錄與托盤互動。
"""

import os
import sys
import threading
import time
import tkinter as tk
from datetime import datetime, timezone
from tkinter import messagebox, ttk
from typing import Callable, Dict, List, Optional

from PIL import ImageTk
from autostart import (
    check_autostart_status,
    is_autostart_enabled,
    set_autostart,
)
from config_manager import ConfigManager
from ntp_client import NTPClient
from scheduler import TimeSyncScheduler
from time_syncer import TimeSyncer, is_admin, request_admin_elevation
from tray_icon import TrayIconManager, create_default_icon_image

# UI 配色常數 (現代深色科技感主題)
BG_DARK = "#0F172A"       # 主背景 (Slate 900)
CARD_BG = "#1E293B"       # 卡片背景 (Slate 800)
CARD_BORDER = "#334155"   # 卡片邊框 (Slate 700)
TEXT_PRIMARY = "#F8FAFC"  # 主要文字 (Slate 50)
TEXT_SECONDARY = "#94A3B8"# 次要文字 (Slate 400)
TEXT_MUTED = "#64748B"    # 輔助文字 (Slate 500)
ACCENT_BLUE = "#3B82F6"   # 強調藍色 (Blue 500)
ACCENT_BLUE_HOVER = "#2563EB"
SUCCESS_GREEN = "#10B981" # 成功綠色 (Emerald 500)
WARNING_YELLOW = "#F59E0B"# 警告黃色 (Amber 500)
DANGER_RED = "#EF4444"    # 失敗紅色 (Red 500)
INPUT_BG = "#0B1120"      # 輸入框背景
LOG_BG = "#090D16"        # 日誌終端背景
LOG_FG = "#E2E8F0"        # 日誌文字顏色


class ModernTimeSyncGUI:
    """現代化時間同步程式視窗介面"""

    def __init__(self, root: tk.Tk, config_mgr: ConfigManager):
        self.root = root
        self.config_mgr = config_mgr
        self.root.title("Windows 網路自動校時工具")
        self.root.geometry("820x760")
        self.root.minsize(780, 680)
        self.root.configure(bg=BG_DARK)

        # 設定視窗與工具列圖示
        try:
            icon_img = create_default_icon_image(64, 64)
            self._tk_icon = ImageTk.PhotoImage(icon_img)
            self.root.iconphoto(True, self._tk_icon)
        except Exception:
            pass

        # 初始化核心物件
        self.syncer = TimeSyncer(timeout=3.5)
        self.scheduler = TimeSyncScheduler(
            syncer=self.syncer,
            interval_value=self.config_mgr.get("interval_value", 30),
            interval_unit=self.config_mgr.get("interval_unit", "minutes"),
            server_provider=self._get_current_server_target,
            threshold_provider=self._get_current_threshold,
            http_fallback_provider=lambda: self.var_enable_http_fallback.get(),
            http_servers_provider=lambda: self.config_mgr.get("http_fallback_servers", None),
            on_sync_start=self._on_sync_start_callback,
            on_sync_finish=self._on_sync_finish_callback,
            on_tick=self._on_tick_callback,
        )

        # 系統匣管理器
        self.tray_mgr = TrayIconManager(
            app_title="Windows 網路自動校時工具",
            on_show_window=self.show_window,
            on_sync_now=self.trigger_sync_now,
            on_toggle_auto_sync=self.toggle_auto_sync,
            is_auto_sync_active=lambda: self.scheduler.is_running,
            get_status_text=lambda: self.scheduler.get_remaining_formatted(),
            on_exit=self.quit_app,
        )

        # 介面變數
        self.var_auto_sync = tk.BooleanVar(
            value=self.config_mgr.get("auto_sync", True)
        )
        self.var_interval_val = tk.StringVar(
            value=str(self.config_mgr.get("interval_value", 30))
        )
        self.var_interval_unit = tk.StringVar(
            value=self.config_mgr.get("interval_unit", "minutes")
        )
        self.var_threshold_enabled = tk.BooleanVar(
            value=self.config_mgr.get("threshold_sync_enabled", False)
        )
        self.var_threshold_sec = tk.StringVar(
            value=str(self.config_mgr.get("threshold_seconds", 60))
        )
        self.var_selected_server = tk.StringVar(
            value=self.config_mgr.get("selected_server", "tock.stdtime.gov.tw")
        )
        self.var_use_fallback = tk.BooleanVar(
            value=self.config_mgr.get("use_fallback", True)
        )
        self.var_enable_http_fallback = tk.BooleanVar(
            value=self.config_mgr.get("enable_http_fallback", True)
        )
        self.var_auto_start = tk.BooleanVar(
            value=is_autostart_enabled()
        )
        self.var_min_to_tray = tk.BooleanVar(
            value=self.config_mgr.get("minimize_to_tray", True)
        )
        self.var_show_notifications = tk.BooleanVar(
            value=self.config_mgr.get("show_notifications", True)
        )

        # 狀態顯示變數
        self.var_clock_time = tk.StringVar(value="--:--:--")
        self.var_clock_date = tk.StringVar(value="----/--/--")
        self.var_status_badge = tk.StringVar(value="待命中")
        self.var_protocol = tk.StringVar(value="🟢 NTP (UDP 123)")
        self.var_last_sync = tk.StringVar(value="尚未同步")
        self.var_offset_ms = tk.StringVar(value="-- ms")
        self.var_delay_ms = tk.StringVar(value="-- ms")
        self.var_countdown = tk.StringVar(value="--:--")
        self.var_active_server = tk.StringVar(
            value=self.config_mgr.get("selected_server", "tock.stdtime.gov.tw")
        )

        # 載入樣式與佈局
        self._setup_styles()
        self._build_ui()

        # 視窗事件攔截
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_button_clicked)

        # 啟動系統匣
        self.tray_mgr.start()

        # 啟動即時時鐘更新定時器
        self._update_live_clock()

        # 若設定自動同步則啟動排程器
        if self.var_auto_sync.get():
            self.scheduler.start(
                sync_immediately=self.config_mgr.get("sync_on_startup", True)
            )

    def _setup_styles(self):
        """配置 ttk 現代化外觀樣式"""
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # 全域配置
        style.configure(".", background=BG_DARK, foreground=TEXT_PRIMARY)

        # TCombobox
        style.configure(
            "Dark.TCombobox",
            fieldbackground=INPUT_BG,
            background=CARD_BORDER,
            foreground=TEXT_PRIMARY,
            darkcolor=CARD_BORDER,
            lightcolor=CARD_BORDER,
            arrowcolor=TEXT_PRIMARY,
            bordercolor=CARD_BORDER,
            padding=5,
        )
        style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", INPUT_BG)],
            selectbackground=[("readonly", ACCENT_BLUE)],
            selectforeground=[("readonly", TEXT_PRIMARY)],
        )

    def _create_card(self, parent, title: str = "") -> tk.Frame:
        """建立具備現代深色卡片外觀的容器"""
        card = tk.Frame(
            parent,
            bg=CARD_BG,
            bd=1,
            relief="solid",
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
        )
        if title:
            header_frame = tk.Frame(card, bg=CARD_BG)
            header_frame.pack(fill="x", padx=14, pady=(10, 6))

            # 裝飾色條
            bar = tk.Frame(header_frame, bg=ACCENT_BLUE, width=4, height=14)
            bar.pack(side="left", padx=(0, 8))

            title_lbl = tk.Label(
                header_frame,
                text=title,
                font=("Microsoft JhengHei UI", 10, "bold"),
                fg=TEXT_PRIMARY,
                bg=CARD_BG,
            )
            title_lbl.pack(side="left")

        return card

    def _build_ui(self):
        """建構主要視窗 UI"""
        main_container = tk.Frame(self.root, bg=BG_DARK)
        main_container.pack(fill="both", expand=True, padx=16, pady=14)

        # 1. 頂部標題與管理員狀態區
        self._build_header(main_container)

        # 2. 上方：即時時鐘與同步狀態儀表卡片
        self._build_dashboard_card(main_container)

        # 3. 中間：排程頻率設定卡片 與 NTP 伺服器設定卡片 (雙欄配置)
        settings_frame = tk.Frame(main_container, bg=BG_DARK)
        settings_frame.pack(fill="x", pady=(0, 10))
        settings_frame.columnconfigure(0, weight=1)
        settings_frame.columnconfigure(1, weight=1)

        self._build_schedule_card(settings_frame)
        self._build_ntp_card(settings_frame)

        # 4. 下方：系統選項與操作按鈕區
        self._build_actions_and_options(main_container)

        # 5. 底部：即時同步記錄日誌終端
        self._build_log_console(main_container)

    def _build_header(self, parent):
        """建構頂部 Header 欄位"""
        header = tk.Frame(parent, bg=BG_DARK)
        header.pack(fill="x", pady=(0, 10))

        # 左側標題
        title_box = tk.Frame(header, bg=BG_DARK)
        title_box.pack(side="left")

        lbl_app_name = tk.Label(
            title_box,
            text="⚡ Windows 網路自動校時工具",
            font=("Microsoft JhengHei UI", 14, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_DARK,
        )
        lbl_app_name.pack(anchor="w")

        lbl_sub = tk.Label(
            title_box,
            text="高精確度 NTP / SNTP 系統時鐘自動同步器",
            font=("Microsoft JhengHei UI", 8),
            fg=TEXT_MUTED,
            bg=BG_DARK,
        )
        lbl_sub.pack(anchor="w")

        # 右側管理員權限狀態徽章
        admin_box = tk.Frame(header, bg=BG_DARK)
        admin_box.pack(side="right", fill="y")

        if is_admin():
            badge = tk.Label(
                admin_box,
                text="🛡️ 已取得系統管理員權限",
                font=("Microsoft JhengHei UI", 9, "bold"),
                fg=SUCCESS_GREEN,
                bg="#064E3B",
                padx=10,
                pady=4,
                relief="flat",
            )
            badge.pack(side="right")
        else:
            btn_elevate = tk.Button(
                admin_box,
                text="⚠️ 權限不足：點擊以管理員權限重啟",
                font=("Microsoft JhengHei UI", 9, "bold"),
                fg="#FFFFFF",
                bg=WARNING_YELLOW,
                activebackground="#D97706",
                activeforeground="#FFFFFF",
                bd=0,
                padx=10,
                pady=4,
                cursor="hand2",
                command=self._elevate_and_restart,
            )
            btn_elevate.pack(side="right")

    def _build_dashboard_card(self, parent):
        """建構即時時鐘與同步狀態儀表卡片"""
        card = self._create_card(parent)
        card.pack(fill="x", pady=(0, 10))

        inner = tk.Frame(card, bg=CARD_BG)
        inner.pack(fill="x", padx=16, pady=12)
        inner.columnconfigure(0, weight=4)
        inner.columnconfigure(1, weight=5)

        # 左側：動態即時大時鐘
        clock_box = tk.Frame(inner, bg="#111827", bd=1, relief="solid", highlightbackground=CARD_BORDER, highlightthickness=1)
        clock_box.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=2)

        lbl_clock_title = tk.Label(
            clock_box,
            text="🕒 本地系統目前時間",
            font=("Microsoft JhengHei UI", 9),
            fg=TEXT_SECONDARY,
            bg="#111827",
        )
        lbl_clock_title.pack(anchor="w", padx=14, pady=(8, 0))

        lbl_time = tk.Label(
            clock_box,
            textvariable=self.var_clock_time,
            font=("Consolas", 24, "bold"),
            fg="#38BDF8",  # 亮藍色時鐘字
            bg="#111827",
        )
        lbl_time.pack(padx=14, pady=(2, 0))

        lbl_date = tk.Label(
            clock_box,
            textvariable=self.var_clock_date,
            font=("Consolas", 10),
            fg=TEXT_MUTED,
            bg="#111827",
        )
        lbl_date.pack(padx=14, pady=(0, 8))

        # 右側：狀態儀表板數值 (2x2 Grid)
        metrics_box = tk.Frame(inner, bg=CARD_BG)
        metrics_box.grid(row=0, column=1, sticky="nsew")
        metrics_box.columnconfigure(0, weight=1)
        metrics_box.columnconfigure(1, weight=1)

        # 區塊 1: 狀態 / 下次同步倒數
        f1 = tk.Frame(metrics_box, bg="#1E293B")
        f1.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        tk.Label(f1, text="下次自動同步倒數", font=("Microsoft JhengHei UI", 8), fg=TEXT_SECONDARY, bg="#1E293B").pack(anchor="w", padx=8, pady=(4, 0))
        self.lbl_countdown_val = tk.Label(f1, textvariable=self.var_countdown, font=("Consolas", 13, "bold"), fg=ACCENT_BLUE, bg="#1E293B")
        self.lbl_countdown_val.pack(anchor="w", padx=8, pady=(0, 4))

        # 區塊 2: 上次同步時間
        f2 = tk.Frame(metrics_box, bg="#1E293B")
        f2.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        tk.Label(f2, text="上次校時時間", font=("Microsoft JhengHei UI", 8), fg=TEXT_SECONDARY, bg="#1E293B").pack(anchor="w", padx=8, pady=(4, 0))
        tk.Label(f2, textvariable=self.var_last_sync, font=("Consolas", 10, "bold"), fg=TEXT_PRIMARY, bg="#1E293B").pack(anchor="w", padx=8, pady=(2, 4))

        # 區塊 3: 時間誤差 Offset
        f3 = tk.Frame(metrics_box, bg="#1E293B")
        f3.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        tk.Label(f3, text="校正時間偏差 (Offset)", font=("Microsoft JhengHei UI", 8), fg=TEXT_SECONDARY, bg="#1E293B").pack(anchor="w", padx=8, pady=(4, 0))
        tk.Label(f3, textvariable=self.var_offset_ms, font=("Consolas", 11, "bold"), fg=SUCCESS_GREEN, bg="#1E293B").pack(anchor="w", padx=8, pady=(0, 4))

        # 區塊 4: 網路延遲 Delay
        f4 = tk.Frame(metrics_box, bg="#1E293B")
        f4.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
        tk.Label(f4, text="往返網路延遲 (RTT)", font=("Microsoft JhengHei UI", 8), fg=TEXT_SECONDARY, bg="#1E293B").pack(anchor="w", padx=8, pady=(4, 0))
        tk.Label(f4, textvariable=self.var_delay_ms, font=("Consolas", 11, "bold"), fg="#FCD34D", bg="#1E293B").pack(anchor="w", padx=8, pady=(0, 4))

        # 底部狀態列：校時協定與通道狀態
        proto_bar = tk.Frame(card, bg="#0B1120", bd=0)
        proto_bar.pack(fill="x", padx=16, pady=(0, 10))

        tk.Label(
            proto_bar,
            text="📡 校時通訊協定：",
            font=("Microsoft JhengHei UI", 8),
            fg=TEXT_MUTED,
            bg="#0B1120",
        ).pack(side="left", padx=(8, 2), pady=4)

        tk.Label(
            proto_bar,
            textvariable=self.var_protocol,
            font=("Microsoft JhengHei UI", 8, "bold"),
            fg="#67E8F9",
            bg="#0B1120",
        ).pack(side="left", pady=4)

        tk.Label(
            proto_bar,
            text=" |  🎯 目標伺服器：",
            font=("Microsoft JhengHei UI", 8),
            fg=TEXT_MUTED,
            bg="#0B1120",
        ).pack(side="left", padx=(8, 2), pady=4)

        tk.Label(
            proto_bar,
            textvariable=self.var_active_server,
            font=("Consolas", 8, "bold"),
            fg=TEXT_SECONDARY,
            bg="#0B1120",
        ).pack(side="left", pady=4)

    def _build_schedule_card(self, parent):
        """建構左半部：更新頻率與排程卡片"""
        card = self._create_card(parent, title="⏱️ 自動更新頻率排程")
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        body = tk.Frame(card, bg=CARD_BG)
        body.pack(fill="both", expand=True, padx=14, pady=8)

        # 啟用開關 Checkbutton
        chk_auto = tk.Checkbutton(
            body,
            text="啟用自動背景定時同步",
            variable=self.var_auto_sync,
            font=("Microsoft JhengHei UI", 9, "bold"),
            fg=TEXT_PRIMARY,
            bg=CARD_BG,
            activebackground=CARD_BG,
            activeforeground=TEXT_PRIMARY,
            selectcolor=INPUT_BG,
            command=self._on_auto_sync_toggled,
        )
        chk_auto.pack(anchor="w", pady=(0, 8))

        # 頻率輸入區
        freq_row = tk.Frame(body, bg=CARD_BG)
        freq_row.pack(fill="x", pady=(0, 8))

        tk.Label(
            freq_row,
            text="更新間隔：每",
            font=("Microsoft JhengHei UI", 9),
            fg=TEXT_SECONDARY,
            bg=CARD_BG,
        ).pack(side="left")

        # 數值輸入框
        ent_val = tk.Entry(
            freq_row,
            textvariable=self.var_interval_val,
            width=6,
            font=("Consolas", 10, "bold"),
            bg=INPUT_BG,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            bd=1,
            relief="solid",
            highlightbackground=CARD_BORDER,
            highlightcolor=ACCENT_BLUE,
            justify="center",
        )
        ent_val.pack(side="left", padx=6)

        # 單位選單
        unit_map = {
            "minutes": "分鐘 (Minutes)",
            "hours": "小時 (Hours)",
            "days": "天 (Days)",
            "seconds": "秒 (Seconds)",
        }
        self.unit_combo_values = list(unit_map.values())
        self.unit_combo_keys = list(unit_map.keys())

        # 目前選中項目的顯示字串
        curr_unit_display = unit_map.get(
            self.var_interval_unit.get(), "分鐘 (Minutes)"
        )
        self.var_unit_display = tk.StringVar(value=curr_unit_display)

        cbo_unit = ttk.Combobox(
            freq_row,
            textvariable=self.var_unit_display,
            values=self.unit_combo_values,
            state="readonly",
            width=14,
            style="Dark.TCombobox",
        )
        cbo_unit.pack(side="left", padx=4)
        cbo_unit.bind("<<ComboboxSelected>>", self._on_unit_combo_changed)

        # 快速預設頻率按鈕標籤
        tk.Label(
            body,
            text="快速設定常用頻率：",
            font=("Microsoft JhengHei UI", 8),
            fg=TEXT_MUTED,
            bg=CARD_BG,
        ).pack(anchor="w", pady=(4, 2))

        preset_row = tk.Frame(body, bg=CARD_BG)
        preset_row.pack(fill="x", pady=(0, 6))

        presets = [
            ("5 分鐘", 5, "minutes"),
            ("15 分鐘", 15, "minutes"),
            ("1 小時", 1, "hours"),
            ("6 小時", 6, "hours"),
            ("1 天", 1, "days"),
        ]

        for text, v, u in presets:
            btn = tk.Button(
                preset_row,
                text=text,
                font=("Microsoft JhengHei UI", 8),
                fg=TEXT_SECONDARY,
                bg="#334155",
                activebackground=ACCENT_BLUE,
                activeforeground=TEXT_PRIMARY,
                bd=0,
                padx=6,
                pady=2,
                cursor="hand2",
                command=lambda val=v, unit=u: self._apply_preset_interval(val, unit),
            )
            btn.pack(side="left", padx=(0, 4))

        # 智慧閾值校時模式 (誤差超過設定秒數/1分鐘才同步)
        thresh_card = tk.Frame(body, bg="#111827", bd=1, relief="solid", highlightbackground=CARD_BORDER, highlightthickness=1)
        thresh_card.pack(fill="x", pady=(6, 0))

        thresh_inner = tk.Frame(thresh_card, bg="#111827", padx=8, pady=6)
        thresh_inner.pack(fill="x")

        chk_thresh = tk.Checkbutton(
            thresh_inner,
            text="僅在時間誤差超過閾值時才寫入時鐘",
            variable=self.var_threshold_enabled,
            font=("Microsoft JhengHei UI", 8, "bold"),
            fg="#38BDF8",
            bg="#111827",
            activebackground="#111827",
            activeforeground="#38BDF8",
            selectcolor=INPUT_BG,
            command=self._on_threshold_toggled,
        )
        chk_thresh.pack(anchor="w")

        thresh_row = tk.Frame(thresh_inner, bg="#111827")
        thresh_row.pack(fill="x", pady=(3, 0))

        tk.Label(
            thresh_row,
            text="  └ 誤差超過：",
            font=("Microsoft JhengHei UI", 8),
            fg=TEXT_SECONDARY,
            bg="#111827",
        ).pack(side="left")

        ent_thresh = tk.Entry(
            thresh_row,
            textvariable=self.var_threshold_sec,
            width=5,
            font=("Consolas", 9, "bold"),
            bg=INPUT_BG,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            bd=1,
            relief="solid",
            highlightbackground=CARD_BORDER,
            justify="center",
        )
        ent_thresh.pack(side="left", padx=4)

        tk.Label(
            thresh_row,
            text="秒 (預設 60 秒 / 1 分鐘)",
            font=("Microsoft JhengHei UI", 8),
            fg=TEXT_MUTED,
            bg="#111827",
        ).pack(side="left")

    def _build_ntp_card(self, parent):
        """建構右半部：NTP 伺服器設定卡片"""
        card = self._create_card(parent, title="🌐 NTP 伺服器設定")
        card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        body = tk.Frame(card, bg=CARD_BG)
        body.pack(fill="both", expand=True, padx=14, pady=8)

        # 伺服器選單列
        server_row = tk.Frame(body, bg=CARD_BG)
        server_row.pack(fill="x", pady=(0, 6))

        self.server_items = self.config_mgr.get_all_servers()
        self.server_display_list = [
            f"{s['name']} [{s['host']}]" for s in self.server_items
        ]

        # 尋找當前選中項目的 index
        current_host = self.var_selected_server.get()
        current_display = self.server_display_list[0]
        for idx, s in enumerate(self.server_items):
            if s["host"] == current_host:
                current_display = self.server_display_list[idx]
                break

        self.var_server_display = tk.StringVar(value=current_display)

        self.cbo_server = ttk.Combobox(
            server_row,
            textvariable=self.var_server_display,
            values=self.server_display_list,
            state="readonly",
            style="Dark.TCombobox",
        )
        self.cbo_server.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.cbo_server.bind("<<ComboboxSelected>>", self._on_server_selected)

        # 測試連線 (Ping) 按鈕
        btn_ping = tk.Button(
            server_row,
            text="📡 測試延遲",
            font=("Microsoft JhengHei UI", 8, "bold"),
            fg=TEXT_PRIMARY,
            bg="#334155",
            activebackground="#475569",
            activeforeground=TEXT_PRIMARY,
            bd=0,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._test_current_server_ping,
        )
        btn_ping.pack(side="right")

        # 備援與自訂伺服器按鈕列
        sub_row = tk.Frame(body, bg=CARD_BG)
        sub_row.pack(fill="x", pady=(2, 0))

        chk_fallback = tk.Checkbutton(
            sub_row,
            text="主伺服器失敗時自動輪詢備援",
            variable=self.var_use_fallback,
            font=("Microsoft JhengHei UI", 8),
            fg=TEXT_SECONDARY,
            bg=CARD_BG,
            activebackground=CARD_BG,
            activeforeground=TEXT_SECONDARY,
            selectcolor=INPUT_BG,
            command=lambda: self.config_mgr.set(
                "use_fallback", self.var_use_fallback.get()
            ),
        )
        chk_fallback.pack(side="left")

        btn_add_custom = tk.Button(
            sub_row,
            text="＋新增自訂",
            font=("Microsoft JhengHei UI", 8),
            fg=ACCENT_BLUE,
            bg=CARD_BG,
            activebackground=CARD_BG,
            activeforeground=TEXT_PRIMARY,
            bd=0,
            cursor="hand2",
            command=self._show_add_server_dialog,
        )
        btn_add_custom.pack(side="right")

        btn_del_custom = tk.Button(
            sub_row,
            text="🗑️ 刪除自訂",
            font=("Microsoft JhengHei UI", 8),
            fg="#F87171",
            bg=CARD_BG,
            activebackground=CARD_BG,
            activeforeground="#EF4444",
            bd=0,
            cursor="hand2",
            command=self._delete_selected_custom_server,
        )
        btn_del_custom.pack(side="right", padx=(0, 6))

        # HTTPS 備援核取方塊列
        http_row = tk.Frame(body, bg=CARD_BG)
        http_row.pack(fill="x", pady=(2, 0))

        chk_http = tk.Checkbutton(
            http_row,
            text="UDP 123 受阻時切換 HTTPS (TCP 443) 備援",
            variable=self.var_enable_http_fallback,
            font=("Microsoft JhengHei UI", 8),
            fg=TEXT_SECONDARY,
            bg=CARD_BG,
            activebackground=CARD_BG,
            activeforeground=TEXT_SECONDARY,
            selectcolor=INPUT_BG,
            command=self._on_http_fallback_toggled,
        )
        chk_http.pack(side="left")

    def _build_actions_and_options(self, parent):
        """建構系統選項勾選區與底部動作按鈕"""
        opt_card = self._create_card(parent)
        opt_card.pack(fill="x", pady=(0, 10))

        inner = tk.Frame(opt_card, bg=CARD_BG)
        inner.pack(fill="x", padx=14, pady=10)

        # 系統選項 Checkboxes
        opts_box = tk.Frame(inner, bg=CARD_BG)
        opts_box.pack(side="left", fill="x", expand=True)

        chk_autostart = tk.Checkbutton(
            opts_box,
            text="開機自動啟動 (常駐於系統匣)",
            variable=self.var_auto_start,
            font=("Microsoft JhengHei UI", 9),
            fg=TEXT_PRIMARY,
            bg=CARD_BG,
            activebackground=CARD_BG,
            activeforeground=TEXT_PRIMARY,
            selectcolor=INPUT_BG,
            command=self._on_autostart_toggled,
        )
        chk_autostart.grid(row=0, column=0, sticky="w", padx=(0, 12), pady=2)

        chk_min_tray = tk.Checkbutton(
            opts_box,
            text="點擊關閉視窗 (X) 時縮小至系統匣",
            variable=self.var_min_to_tray,
            font=("Microsoft JhengHei UI", 9),
            fg=TEXT_PRIMARY,
            bg=CARD_BG,
            activebackground=CARD_BG,
            activeforeground=TEXT_PRIMARY,
            selectcolor=INPUT_BG,
            command=lambda: self.config_mgr.set(
                "minimize_to_tray", self.var_min_to_tray.get()
            ),
        )
        chk_min_tray.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=2)

        chk_notify = tk.Checkbutton(
            opts_box,
            text="校時完成發送桌面通知",
            variable=self.var_show_notifications,
            font=("Microsoft JhengHei UI", 9),
            fg=TEXT_PRIMARY,
            bg=CARD_BG,
            activebackground=CARD_BG,
            activeforeground=TEXT_PRIMARY,
            selectcolor=INPUT_BG,
            command=lambda: self.config_mgr.set(
                "show_notifications", self.var_show_notifications.get()
            ),
        )
        chk_notify.grid(row=0, column=2, sticky="w", pady=2)

        # 右側動作按鈕組
        btn_box = tk.Frame(inner, bg=CARD_BG)
        btn_box.pack(side="right")

        # 立即同步按鈕 (主亮色按鈕)
        self.btn_sync_now = tk.Button(
            btn_box,
            text="⚡ 立即同步時間",
            font=("Microsoft JhengHei UI", 10, "bold"),
            fg="#FFFFFF",
            bg=ACCENT_BLUE,
            activebackground=ACCENT_BLUE_HOVER,
            activeforeground="#FFFFFF",
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self.trigger_sync_now,
        )
        self.btn_sync_now.pack(side="right", padx=(8, 0))

        # 套用設定按鈕
        btn_save = tk.Button(
            btn_box,
            text="💾 套用頻率設定",
            font=("Microsoft JhengHei UI", 9),
            fg=TEXT_PRIMARY,
            bg="#334155",
            activebackground="#475569",
            activeforeground=TEXT_PRIMARY,
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            command=self._apply_schedule_settings,
        )
        btn_save.pack(side="right")

    def _build_log_console(self, parent):
        """建構日誌終端區塊"""
        card = self._create_card(parent, title="📜 即時校時日誌記錄 (Log)")
        card.pack(fill="both", expand=True)

        header_actions = tk.Frame(card, bg=CARD_BG)
        header_actions.place(relx=1.0, y=10, anchor="ne", x=-14)

        btn_clear_log = tk.Button(
            header_actions,
            text="清空記錄",
            font=("Microsoft JhengHei UI", 8),
            fg=TEXT_MUTED,
            bg=CARD_BG,
            activebackground=CARD_BG,
            activeforeground=TEXT_PRIMARY,
            bd=0,
            cursor="hand2",
            command=self._clear_logs,
        )
        btn_clear_log.pack(side="right")

        log_body = tk.Frame(card, bg=CARD_BG)
        log_body.pack(fill="both", expand=True, padx=14, pady=(4, 12))

        # Text 終端
        self.txt_log = tk.Text(
            log_body,
            bg=LOG_BG,
            fg=LOG_FG,
            insertbackground=TEXT_PRIMARY,
            font=("Consolas", 9),
            wrap="word",
            bd=1,
            relief="solid",
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
        )
        self.txt_log.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(
            log_body, orient="vertical", command=self.txt_log.yview, bg=CARD_BG
        )
        scrollbar.pack(side="right", fill="y")
        self.txt_log.config(yscrollcommand=scrollbar.set)

        # 標籤樣式
        self.txt_log.tag_config("info", foreground="#93C5FD")
        self.txt_log.tag_config("success", foreground="#34D399")
        self.txt_log.tag_config("warning", foreground="#FBBF24")
        self.txt_log.tag_config("error", foreground="#F87171")
        self.txt_log.tag_config("timestamp", foreground="#64748B")

        # 初始歡迎 log
        self.log("程式啟動完成，初始化時間同步排程服務...", level="info")

    def log(self, message: str, level: str = "info"):
        """輸出日誌到控制台視窗"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.txt_log.config(state="normal")
        self.txt_log.insert("end", f"[{timestamp}] ", "timestamp")
        self.txt_log.insert("end", f"{message}\n", level)
        self.txt_log.see("end")
        self.txt_log.config(state="disabled")

    def _clear_logs(self):
        """清空日誌文字"""
        self.txt_log.config(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.config(state="disabled")

    def _update_live_clock(self):
        """每 200 毫秒刷新本地時鐘顯示"""
        now = datetime.now()
        self.var_clock_time.set(now.strftime("%H:%M:%S"))
        self.var_clock_date.set(now.strftime("%Y/%m/%d (%a)"))
        self.root.after(200, self._update_live_clock)

    def _on_tick_callback(self, rem_seconds: float, rem_str: str):
        """排程器每秒 tick 回呼 (背景線程觸發，透過 root.after 安全更新 UI)"""

        def _update():
            if self.scheduler.is_running:
                self.var_countdown.set(rem_str)
            else:
                self.var_countdown.set("已暫停")

        self.root.after(0, _update)

    def _on_sync_start_callback(self):
        """同步開始回呼"""

        def _update():
            self.var_countdown.set("同步中...")
            self.btn_sync_now.config(
                text="⏳ 同步中...", state="disabled", bg="#475569"
            )
            self.log("開始向 NTP 伺服器查詢並校正系統時間...", level="info")

        self.root.after(0, _update)

    def _get_current_threshold(self) -> Optional[float]:
        """取得供排程器查詢的誤差閾值秒數"""
        if self.var_threshold_enabled.get():
            try:
                val = float(self.var_threshold_sec.get())
                return val if val > 0 else 60.0
            except ValueError:
                return 60.0
        return None

    def _on_threshold_toggled(self):
        """誤差閾值模式 Checkbox 事件"""
        enabled = self.var_threshold_enabled.get()
        self.config_mgr.set("threshold_sync_enabled", enabled)
        if enabled:
            try:
                sec = float(self.var_threshold_sec.get())
            except ValueError:
                sec = 60.0
            self.log(
                f"已啟用智慧閾值模式：系統時鐘誤差超過 {sec:.0f} 秒 (1分鐘) 時才寫入同步",
                level="info",
            )
        else:
            self.log("已停用智慧閾值模式：定時自動強制寫入同步", level="info")

    def _on_http_fallback_toggled(self):
        """HTTPS 備援模式 Checkbox 事件"""
        enabled = self.var_enable_http_fallback.get()
        self.config_mgr.set("enable_http_fallback", enabled)
        if enabled:
            self.log(
                "已啟用 HTTPS (TCP 443) 備援校時：當 UDP 123 受限或遭網管封鎖時自動切換",
                level="info",
            )
        else:
            self.log(
                "已停用 HTTPS 備援校時：僅使用標準 NTP (UDP 123)",
                level="warning",
            )

    def _on_sync_finish_callback(self, result: Dict):
        """同步完成回呼"""

        def _update():
            self.btn_sync_now.config(
                text="⚡ 立即同步時間", state="normal", bg=ACCENT_BLUE
            )
            if result.get("success"):
                offset_ms = result.get("offset_ms")
                delay_ms = result.get("delay_ms")
                time_str = result.get("time_str", "")
                protocol = result.get("protocol", "NTP")
                is_fallback = result.get("is_fallback", False)

                # 更新協定與通道狀態標籤
                if is_fallback:
                    self.var_protocol.set("🌐 HTTPS 備援 (TCP 443)")
                else:
                    self.var_protocol.set(f"🟢 {protocol} (UDP 123)")

                self.var_offset_ms.set(f"{offset_ms} ms" if offset_ms is not None else "--")
                self.var_delay_ms.set(f"{delay_ms} ms" if delay_ms is not None else "--")

                if result.get("skipped"):
                    # 誤差未達閾值，略過寫入
                    self.var_last_sync.set(f"{time_str} (精準)")
                    msg = result.get("message", "時間偏差小於閾值，略過寫入")
                    self.log(f"ℹ️ {msg}", level="warning")
                else:
                    # 成功寫入
                    self.var_last_sync.set(time_str)
                    msg = result.get("message", "校時成功")
                    if is_fallback:
                        self.log(f"🌐 {msg}", level="warning")
                    else:
                        self.log(f"✅ {msg}", level="success")

                    if self.var_show_notifications.get():
                        notify_suffix = " (透過 HTTPS 備援)" if is_fallback else ""
                        self.tray_mgr.notify(
                            f"校時成功{notify_suffix}！已修正時間誤差 {offset_ms} ms",
                            title="Windows 自動校時工具",
                        )
            else:
                err = result.get("error", "未知錯誤")
                self.log(f"❌ 校時失敗: {err}", level="error")

                if result.get("need_admin"):
                    self.log(
                        "提示：修改 Windows 系統時間需要管理員權限，請點擊上方黃色按鈕以管理員身分重啟。",
                        level="warning",
                    )

                if self.var_show_notifications.get():
                    self.tray_mgr.notify(
                        f"校時失敗: {err}",
                        title="Windows 自動校時工具",
                    )

        self.root.after(0, _update)

    def _get_current_server_target(self):
        """取得供排程器查詢的伺服器 (若啟用 fallback 則傳入列表)"""
        primary = self.var_selected_server.get()
        if not self.var_use_fallback.get():
            return primary

        # 包含備援伺服器
        all_hosts = [
            s["host"] for s in self.config_mgr.get_all_servers()
        ]
        # 把 primary 放在第一個
        fallback_list = [primary] + [h for h in all_hosts if h != primary]
        return fallback_list

    def trigger_sync_now(self):
        """手動觸發立即同步 (強制寫入)"""
        self.scheduler.trigger_now_async(force=True)

    def toggle_auto_sync(self):
        """切換自動同步啟用/暫停狀態"""
        new_val = not self.var_auto_sync.get()
        self.var_auto_sync.set(new_val)
        self._on_auto_sync_toggled()

    def _on_auto_sync_toggled(self):
        """自動同步 Checkbox 切換事件"""
        enabled = self.var_auto_sync.get()
        self.config_mgr.set("auto_sync", enabled)
        if enabled:
            if not self.scheduler.is_running:
                self.scheduler.start()
            else:
                self.scheduler.resume()
            self.log("已啟用背景定時自動校時服務", level="info")
        else:
            self.scheduler.pause()
            self.var_countdown.set("已暫停")
            self.log("已暫停自動校時服務", level="warning")
        self.tray_mgr.update_menu()

    def _on_unit_combo_changed(self, event=None):
        """更新頻率單位選單變更"""
        selected_display = self.var_unit_display.get()
        idx = self.unit_combo_values.index(selected_display)
        unit_key = self.unit_combo_keys[idx]
        self.var_interval_unit.set(unit_key)

    def _apply_preset_interval(self, val: int, unit: str):
        """套用常用預設頻率"""
        self.var_interval_val.set(str(val))
        self.var_interval_unit.set(unit)
        unit_map = {
            "minutes": "分鐘 (Minutes)",
            "hours": "小時 (Hours)",
            "days": "天 (Days)",
            "seconds": "秒 (Seconds)",
        }
        self.var_unit_display.set(unit_map.get(unit, "分鐘 (Minutes)"))
        self._apply_schedule_settings()

    def _apply_schedule_settings(self):
        """套用並儲存頻率與閾值設定"""
        try:
            val = int(self.var_interval_val.get())
            if val <= 0:
                raise ValueError("頻率數值必須大於 0")
        except ValueError:
            messagebox.showerror(
                "設定錯誤", "更新間隔數值請輸入大於 0 的正整數！"
            )
            return

        try:
            thresh_val = int(self.var_threshold_sec.get())
            if thresh_val < 0:
                raise ValueError("閾值數值不能小於 0")
        except ValueError:
            messagebox.showerror(
                "設定錯誤", "誤差閾值請輸入大於或等於 0 的秒數！"
            )
            return

        unit = self.var_interval_unit.get()
        self.config_mgr.set("interval_value", val)
        self.config_mgr.set("interval_unit", unit)
        self.config_mgr.set("threshold_sync_enabled", self.var_threshold_enabled.get())
        self.config_mgr.set("threshold_seconds", thresh_val)

        self.scheduler.update_interval(val, unit)
        unit_str = self.var_unit_display.get()
        thresh_info = (
            f" (已開啟閾值保護：誤差超過 {thresh_val} 秒才寫入)"
            if self.var_threshold_enabled.get()
            else " (強制寫入模式)"
        )
        self.log(
            f"已成功套用設定：每 {val} {unit_str}{thresh_info}",
            level="success",
        )

    def _on_server_selected(self, event=None):
        """選擇 NTP 伺服器選單事件"""
        selected_idx = self.cbo_server.current()
        if 0 <= selected_idx < len(self.server_items):
            chosen = self.server_items[selected_idx]
            host = chosen["host"]
            self.var_selected_server.set(host)
            self.config_mgr.set("selected_server", host)
            self.log(
                f"已切換主要 NTP 伺服器為：{chosen['name']} ({host})", level="info"
            )

    def _test_current_server_ping(self):
        """測試目前所選伺服器的連線延遲"""
        host = self.var_selected_server.get()
        self.log(f"正在測試 NTP 伺服器 '{host}' 連線延遲...", level="info")

        def _async_test():
            client = NTPClient(timeout=3.0)
            res = client.test_server(host)

            def _done():
                if res.get("success"):
                    self.log(f"測試成功！{res.get('message')}", level="success")
                    messagebox.showinfo(
                        "連線測試成功",
                        f"伺服器：{host}\n"
                        f"伺服器 IP：{res.get('server_ip')}\n"
                        f"網路延遲 (RTT)：{res.get('delay_ms')} ms\n"
                        f"時間誤差 (Offset)：{res.get('offset_ms')} ms\n"
                        f"層級 (Stratum)：{res.get('stratum')}",
                    )
                else:
                    self.log(f"測試失敗！{res.get('message')}", level="error")
                    messagebox.showwarning(
                        "連線測試失敗",
                        f"無法連線至 NTP 伺服器 '{host}'：\n{res.get('message')}",
                    )

            self.root.after(0, _done)

        threading.Thread(target=_async_test, daemon=True).start()

    def _show_add_server_dialog(self):
        """顯示新增自訂 NTP 伺服器對話框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("新增自訂 NTP 伺服器")
        dialog.geometry("400x240")
        dialog.configure(bg=BG_DARK)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        f = tk.Frame(dialog, bg=CARD_BG, padx=16, pady=16)
        f.pack(fill="both", expand=True, padx=12, pady=12)

        tk.Label(
            f, text="伺服器名稱 / 描述：", font=("Microsoft JhengHei UI", 9), fg=TEXT_SECONDARY, bg=CARD_BG
        ).pack(anchor="w")
        ent_name = tk.Entry(f, bg=INPUT_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, bd=1, relief="solid")
        ent_name.pack(fill="x", pady=(2, 10))

        tk.Label(
            f, text="伺服器位址 (域名或 IP，如 time.apple.com)：", font=("Microsoft JhengHei UI", 9), fg=TEXT_SECONDARY, bg=CARD_BG
        ).pack(anchor="w")
        ent_host = tk.Entry(f, bg=INPUT_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, bd=1, relief="solid")
        ent_host.pack(fill="x", pady=(2, 14))

        def _save():
            name = ent_name.get().strip()
            host = ent_host.get().strip()
            if not host:
                messagebox.showerror("錯誤", "伺服器位址不能為空！", parent=dialog)
                return
            success = self.config_mgr.add_custom_server(host, name=name)
            if success:
                # 重新載入下拉清單
                self.server_items = self.config_mgr.get_all_servers()
                self.server_display_list = [
                    f"{s['name']} [{s['host']}]" for s in self.server_items
                ]
                self.cbo_server["values"] = self.server_display_list
                # 選中新增的項目
                new_display = f"{(name if name else '自訂伺服器')} [{host}]"
                self.var_server_display.set(new_display)
                self.var_selected_server.set(host)
                self.config_mgr.set("selected_server", host)
                self.log(f"已新增自訂 NTP 伺服器：{host}", level="success")
                dialog.destroy()
            else:
                messagebox.showwarning(
                    "提示", "該伺服器位址已存在列表中！", parent=dialog
                )

        btn_confirm = tk.Button(
            f,
            text="確認新增",
            font=("Microsoft JhengHei UI", 9, "bold"),
            fg="#FFFFFF",
            bg=ACCENT_BLUE,
            activebackground=ACCENT_BLUE_HOVER,
            bd=0,
            padx=12,
            pady=4,
            command=_save,
        )
        btn_confirm.pack(side="right")

        btn_cancel = tk.Button(
            f,
            text="取消",
            font=("Microsoft JhengHei UI", 9),
            fg=TEXT_SECONDARY,
            bg="#334155",
            bd=0,
            padx=12,
            pady=4,
            command=dialog.destroy,
        )
        btn_cancel.pack(side="right", padx=8)

    def _delete_selected_custom_server(self):
        """刪除目前選中的自訂 NTP 伺服器"""
        selected_host = self.var_selected_server.get()
        custom_servers = self.config_mgr.get("custom_servers", [])

        # 尋找是否為自訂伺服器
        target_custom = None
        for c in custom_servers:
            c_host = c["host"] if isinstance(c, dict) else str(c)
            if c_host.lower() == selected_host.lower():
                target_custom = c
                break

        if not target_custom:
            messagebox.showinfo(
                "無法刪除",
                "目前選中的是系統內建的預設 NTP 伺服器，無法刪除。\n僅能刪除使用者手動新增的自訂伺服器。",
                parent=self.root,
            )
            return

        c_name = (
            target_custom.get("name", selected_host)
            if isinstance(target_custom, dict)
            else selected_host
        )
        confirmed = messagebox.askyesno(
            "確認刪除",
            f"確定要刪除自訂 NTP 伺服器「{c_name}」({selected_host}) 嗎？",
            parent=self.root,
        )
        if not confirmed:
            return

        self.config_mgr.remove_custom_server(selected_host)

        # 重新整理伺服器清單並切換回第一台預設伺服器
        self.server_items = self.config_mgr.get_all_servers()
        self.server_display_list = [
            f"{s['name']} [{s['host']}]" for s in self.server_items
        ]
        self.cbo_server["values"] = self.server_display_list

        first_server = self.server_items[0]
        self.var_server_display.set(self.server_display_list[0])
        self.var_selected_server.set(first_server["host"])
        self.config_mgr.set("selected_server", first_server["host"])

        self.log(f"已成功刪除自訂 NTP 伺服器：{selected_host}", level="info")
        messagebox.showinfo("成功", f"已刪除自訂伺服器：{selected_host}", parent=self.root)

    def _on_autostart_toggled(self):
        """開機自動啟動 Checkbox 事件"""
        enable = self.var_auto_start.get()
        success = set_autostart(enable, start_minimized=True)
        if success:
            self.config_mgr.set("auto_start", enable)
            if enable:
                status = check_autostart_status()
                mode_desc = (
                    "已註冊 Windows 工作排程器 (以最高管理員權限靜默啟動，開機免 UAC 彈窗)"
                    if status.get("task_scheduler_enabled")
                    else "已寫入 Windows 登錄檔 (HKCU Run)"
                )
                self.log(
                    f"已啟用開機自動啟動 ({mode_desc})",
                    level="success",
                )
            else:
                self.log("已停用開機自動啟動 (已清除工作排程與登錄檔項目)", level="info")
        else:
            self.var_auto_start.set(not enable)
            messagebox.showerror("錯誤", "設定開機啟動失敗，請檢查系統權限。")

    def _elevate_and_restart(self):
        """以系統管理員權限重啟程式"""
        if is_admin():
            messagebox.showinfo("提示", "目前已是系統管理員權限！")
            return
        if messagebox.askyesno(
            "提升管理員權限",
            "是否要以系統管理員身分重新啟動本程式？\n（只有管理員權限才能直接寫入修改 Windows 系統時鐘）",
        ):
            try:
                from main import release_single_instance
                release_single_instance()
            except Exception:
                pass
            ok = request_admin_elevation(["--restarting"])
            if ok:
                self.quit_app()

    def _on_close_button_clicked(self):
        """使用者點擊右上角 X 關閉按鈕"""
        if self.var_min_to_tray.get():
            self.hide_window()
            self.tray_mgr.notify(
                "程式已縮小至右下角系統匣持續在背景定時同步時間。",
                title="Windows 自動校時工具",
            )
        else:
            self.quit_app()

    def hide_window(self):
        """隱藏主視窗至系統匣"""
        self.root.withdraw()

    def show_window(self):
        """從系統匣還原並置頂主視窗"""

        def _do():
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()

        self.root.after(0, _do)

    def quit_app(self):
        """完整關閉應用程式"""
        self.scheduler.stop()
        self.tray_mgr.stop()
        self.root.quit()
        self.root.destroy()
