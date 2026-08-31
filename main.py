"""
Windows 網路自動校時工具主程式進入點 (main.py)
負責處理命令列參數、單一執行個體檢查 (Single Instance Mutex)、權限提權及 GUI 生命週期管理。
"""

import argparse
import ctypes
import os
import sys
import time
import tkinter as tk

from autostart import is_autostart_enabled
from config_manager import ConfigManager
from gui import ModernTimeSyncGUI
from time_syncer import TimeSyncer, is_admin, request_admin_elevation

MUTEX_NAME = "Global\\WindowsTimeAutoUpdate_SingleInstance_Mutex"
ERROR_ALREADY_EXISTS = 183
_CURRENT_MUTEX = None

# 設置 Windows 專屬 AppUserModelID，使工作列獨立顯示應用程式
try:
    myappid = "Ancheng.WindowsTimeAutoUpdate.Desktop.1.0"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass


def acquire_single_instance(timeout_sec: float = 2.5):
    """
    透過 Windows Mutex 確保程式只有單一執行個體在背景運作
    支援在重啟/提權交接時等待舊進程釋放鎖 (timeout_sec 秒)
    """
    global _CURRENT_MUTEX
    start_t = time.monotonic()
    
    while True:
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
        last_error = ctypes.windll.kernel32.GetLastError()
        
        if last_error != ERROR_ALREADY_EXISTS:
            _CURRENT_MUTEX = mutex
            return mutex
        
        # 關閉本次衝突的暫存 handle
        if mutex:
            ctypes.windll.kernel32.CloseHandle(mutex)
        
        # 若超時則判定已有其他實例正在運行
        if time.monotonic() - start_t >= timeout_sec:
            return None
        
        time.sleep(0.15)


def release_single_instance():
    """釋放並關閉當前進程持有的 Single Instance Mutex"""
    global _CURRENT_MUTEX
    if _CURRENT_MUTEX and _CURRENT_MUTEX != 1:
        try:
            ctypes.windll.kernel32.CloseHandle(_CURRENT_MUTEX)
        except Exception:
            pass
        _CURRENT_MUTEX = None


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
    parser.add_argument(
        "--restarting",
        action="store_true",
        help="由舊進程重啟/提權啟動之標記",
    )
    parser.add_argument(
        "--no-auto-elevate",
        action="store_true",
        help="不要在啟動時自動彈出 UAC 提權請求",
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
        clean_args = [a for a in sys.argv[1:] if a != "--elevate"] + ["--restarting"]
        request_admin_elevation(clean_args)
        sys.exit(0)

    # 3. 若為打包後的 EXE 或直接啟動且非管理員，自動嘗試進行 UAC 提權啟動 (開機最小化模式除外)
    if not is_admin() and not args.restarting and not args.no_auto_elevate and not args.minimized:
        forward_args = [a for a in sys.argv[1:]] + ["--restarting"]
        elevated = request_admin_elevation(forward_args)
        if elevated:
            # 提權程序已成功喚起，原非管理員進程安靜結束
            sys.exit(0)
        # 若使用者在 UAC 對話框選擇「否」，則繼續以非管理員（唯讀模式）開啟

    # 4. 單一實例檢查 (支援交接等待)
    wait_time = 3.0 if args.restarting else 0.5
    mutex = acquire_single_instance(timeout_sec=wait_time)
    
    if mutex is None:
        # 已有相同程式在背景執行
        root = tk.Tk()
        root.withdraw()
        from tkinter import messagebox

        messagebox.showinfo(
            "提示",
            "Windows 網路自動校時工具已經在背景常駐執行中！\n請檢查螢幕右下角系統匣圖示。",
        )
        root.destroy()
        sys.exit(0)

    # 5. 載入設定
    config_mgr = ConfigManager()

    # 6. 建立並啟動 GUI
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
        release_single_instance()


if __name__ == "__main__":
    main()
