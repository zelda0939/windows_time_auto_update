"""
Windows 開機自動啟動管理模組 (autostart.py)
透過 Windows 登錄檔 (HKCU Run) 設定或解除開機自動常駐於系統匣。
"""

import os
import sys
import winreg
from typing import Optional

REG_RUN_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_KEY = "WindowsTimeAutoUpdate"


def _get_pythonw_path() -> str:
    """取得 pythonw.exe 的絕對路徑 (無控制台黑視窗模式)"""
    py_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(py_dir, "pythonw.exe")
    if os.path.exists(pythonw):
        return pythonw
    return sys.executable


def get_launch_command(start_minimized: bool = True) -> str:
    """
    建構開機時執行的完整命令字串

    :param start_minimized: 是否加上 --minimized 參數
    :return: 命令字串
    """
    extra_arg = " --minimized" if start_minimized else ""

    if getattr(sys, "frozen", False):
        # 打包成 exe 的情況
        exe_path = os.path.abspath(sys.executable)
        return f'"{exe_path}"{extra_arg}'
    else:
        # Python 腳本模式，使用 pythonw.exe
        python_exe = _get_pythonw_path()
        main_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "main.py"
        )
        return f'"{python_exe}" "{main_script}"{extra_arg}'


def is_autostart_enabled() -> bool:
    """檢查目前登錄檔中是否已啟用開機自動啟動"""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_RUN_PATH, 0, winreg.KEY_READ
        ) as key:
            value, _ = winreg.QueryValueEx(key, APP_REG_KEY)
            return bool(value)
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"讀取開機啟動登錄檔失敗: {e}")
        return False


def set_autostart(enable: bool, start_minimized: bool = True) -> bool:
    """
    啟用或停用開機自動啟動

    :param enable: True 為啟用，False 為停用
    :param start_minimized: 啟用時是否預設最小化到系統匣
    :return: 操作是否成功
    """
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_RUN_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enable:
                cmd = get_launch_command(start_minimized)
                winreg.SetValueEx(key, APP_REG_KEY, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, APP_REG_KEY)
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        print(f"設定開機啟動登錄檔失敗: {e}")
        return False
