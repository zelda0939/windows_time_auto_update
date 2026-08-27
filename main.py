"""
Windows 網路自動校時工具主程式進入點 (main.py)
負責處理命令列參數、單一執行個體檢查 (Single Instance Mutex)、權限提權及 GUI 生命週期管理。
"""

import argparse
import ctypes
import os
import sys
import tkinter as tk

from autostart import is_autostart_enabled
from config_manager import ConfigManager
from gui import ModernTimeSyncGUI
from time_syncer import TimeSyncer, is_admin, request_admin_elevation

MUTEX_NAME = "Global\\WindowsTimeAutoUpdate_SingleInstance_Mutex"
ERROR_ALREADY_EXISTS = 183

# 設置 Windows 專屬 AppUserModelID，使工作列獨立顯示應用程式
try:
    myappid = "Ancheng.WindowsTimeAutoUpdate.Desktop.1.0"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass


def check_single_instance():
    """透過 Windows Mutex 確保程式只有單一執行個體在背景運作"""
    try:
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
        last_error = ctypes.windll.kernel32.GetLastError()
        if last_error == ERROR_ALREADY_EXISTS:
            return None
        return mutex
    except Exception:
        return 1  # 若建立失敗仍允許執行


def run_sync_once_cli(server: str = "tock.stdtime.gov.tw"):
    """命令列單次校時模式"""
    print(f"[*] 正在向 NTP 伺服器 '{server}' 查詢時間...")
    syncer = TimeSyncer()
    res = syncer.sync_time(server)
    if res.get("success"):
        print(f"[+] 校時成功！")
        print(f"    伺服器: {res.get('server')} ({res.get('server_ip')})")
        print(f"    網路往返延遲: {res.get('delay_ms')} ms")
        print(f"    時間校正誤差: {res.get('offset_ms')} ms")
        print(f"    更新後本地時間: {res.get('time_str')}")
        sys.exit(0)
    else:
        print(f"[-] 校時失敗: {res.get('error')}")
        if res.get("need_admin"):
            print("    請以系統管理員身分執行命令提示字元 (Run as Administrator)。")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Windows 網路自動校時工具 (Windows Auto Time Synchronizer)"
    )
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="啟動時直接最小化常駐至系統匣 (System Tray)，不顯示主視窗",
    )
    parser.add_argument(
        "--sync-once",
        action="store_true",
        help="執行單次時間同步後直接結束 (CLI 模式)",
    )
    parser.add_argument(
        "--server",
        type=str,
        default=None,
        help="指定 NTP 伺服器 (搭配 --sync-once 使用)",
    )
    parser.add_argument(
        "--elevate",
        action="store_true",
        help="自動請求 Windows UAC 管理員提權",
    )
    args = parser.parse_args()

    # 1. 處理 CLI 單次校時模式
    if args.sync_once:
        cm = ConfigManager()
        srv = (
            args.server
            if args.server
            else cm.get("selected_server", "tock.stdtime.gov.tw")
        )
        run_sync_once_cli(srv)
        return

    # 2. 自動提權參數檢查
    if args.elevate and not is_admin():
        clean_args = [a for a in sys.argv[1:] if a != "--elevate"]
        request_admin_elevation(clean_args)
        sys.exit(0)

    # 3. 單一實例檢查
    mutex = check_single_instance()
    if mutex is None:
        # 已有相同程式在背景執行
        # 彈出對話框提示
        root = tk.Tk()
        root.withdraw()
        from tkinter import messagebox

        messagebox.showinfo(
            "提示",
            "Windows 網路自動校時工具已經在背景常駐執行中！\n請檢查螢幕右下角系統匣圖示。",
        )
        root.destroy()
        sys.exit(0)

    # 4. 載入設定
    config_mgr = ConfigManager()

    # 5. 建立並啟動 GUI
    root = tk.Tk()

    # 若需要最小化啟動 (例如開機自動啟動)，先隱藏視窗
    should_start_minimized = args.minimized or config_mgr.get(
        "start_minimized", False
    )
    if should_start_minimized:
        root.withdraw()

    app = ModernTimeSyncGUI(root, config_mgr)

    # 設定視窗置中
    root.update_idletasks()
    w = 820
    h = 760
    ws = root.winfo_screenwidth()
    hs = root.winfo_screenheight()
    x = max(0, (ws // 2) - (w // 2))
    y = max(0, (hs // 2) - (h // 2))
    root.geometry(f"{w}x{h}+{x}+{y}")

    try:
        root.mainloop()
    finally:
        if mutex and mutex != 1:
            ctypes.windll.kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    main()
