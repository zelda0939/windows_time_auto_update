"""
Windows 系統時間同步與權限管理模組 (time_syncer.py)
負責透過 Windows API (SetSystemTime) 寫入系統時鐘，並處理 UAC 管理員權限檢測與提權。
"""

import ctypes
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union
from ntp_client import NTPClient


class SYSTEMTIME(ctypes.Structure):
    """Windows API SYSTEMTIME 結構體"""

    _fields_ = [
        ("wYear", ctypes.c_ushort),
        ("wMonth", ctypes.c_ushort),
        ("wDayOfWeek", ctypes.c_ushort),
        ("wDay", ctypes.c_ushort),
        ("wHour", ctypes.c_ushort),
        ("wMinute", ctypes.c_ushort),
        ("wSecond", ctypes.c_ushort),
        ("wMilliseconds", ctypes.c_ushort),
    ]


def is_admin() -> bool:
    """檢查當前行程是否具有 Windows 系統管理員權限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def request_admin_elevation(params: Optional[List[str]] = None) -> bool:
    """
    要求 Windows UAC 提權，以系統管理員權限重新啟動目前程式

    :param params: 傳遞給新程序的參數列表 (若為 None 則傳入 sys.argv[1:])
    :return: 提權請求是否已成功觸發
    """
    if is_admin():
        return True

    if params is None:
        params = sys.argv[1:]

    # 判斷是否為打包後的 exe 或 python 腳本
    if getattr(sys, "frozen", False):
        executable = sys.executable
        arguments = " ".join([f'"{p}"' for p in params])
    else:
        # 優先使用 pythonw.exe 避免產生黑色控制台終端視窗
        py_dir = os.path.dirname(sys.executable)
        pythonw = os.path.join(py_dir, "pythonw.exe")
        executable = pythonw if os.path.exists(pythonw) else sys.executable
        script = os.path.abspath(sys.argv[0])
        arguments = f'"{script}" ' + " ".join([f'"{p}"' for p in params])

    try:
        # 呼叫 ShellExecuteW 以 'runas' 動詞啟動提權程序
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", executable, arguments, None, 1
        )
        # 若傳回值大於 32 代表執行成功
        return ret > 32
    except Exception as e:
        print(f"UAC 提權請求失敗: {e}")
        return False


def set_windows_time(utc_dt: datetime) -> bool:
    """
    直接呼叫 Windows API SetSystemTime 寫入 UTC 系統時間

    :param utc_dt: 具有 UTC 時區之 datetime 物件
    :return: 是否寫入成功
    """
    # 確保是 UTC 時間
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    else:
        utc_dt = utc_dt.astimezone(timezone.utc)

    st = SYSTEMTIME()
    st.wYear = utc_dt.year
    st.wMonth = utc_dt.month
    # Windows 中 Sunday=0, Monday=1...
    # Python weekday(): Monday=0, Sunday=6
    st.wDayOfWeek = (utc_dt.weekday() + 1) % 7
    st.wDay = utc_dt.day
    st.wHour = utc_dt.hour
    st.wMinute = utc_dt.minute
    st.wSecond = utc_dt.second
    st.wMilliseconds = int(utc_dt.microsecond / 1000)

    res = ctypes.windll.kernel32.SetSystemTime(ctypes.byref(st))
    return res != 0


class TimeSyncer:
    """Windows 時間同步管理類別"""

    def __init__(self, timeout: float = 3.0):
        self.ntp_client = NTPClient(timeout=timeout)

    def sync_time(
        self,
        server_or_servers: Union[str, List[str]],
        threshold_seconds: Optional[float] = None,
    ) -> Dict:
        """
        向 NTP 伺服器查詢並更新 Windows 系統時間

        :param server_or_servers: 單一 NTP 伺服器位址或伺服器列表
        :param threshold_seconds: 誤差閾值 (秒)。若提供且誤差小於此值，則略過寫入
        :return: 同步結果字典
        """
        # 1. 查詢 NTP 時間
        if isinstance(server_or_servers, list):
            query_result = self.ntp_client.query_with_fallback(server_or_servers)
        else:
            query_result = self.ntp_client.query(server_or_servers)

        if not query_result.get("success"):
            return {
                "success": False,
                "server": query_result.get("server"),
                "error": query_result.get("error", "未知 NTP 錯誤"),
                "offset_ms": None,
                "offset_sec": None,
                "delay_ms": None,
                "time_str": None,
                "skipped": False,
            }

        server_name = query_result.get("server")
        offset_ms = query_result.get("offset_ms")
        offset_sec = query_result.get("offset_sec", 0.0)
        delay_ms = query_result.get("delay_ms")
        corrected_utc = query_result.get("corrected_utc_dt")
        corrected_local = query_result.get("corrected_local_dt")
        local_time_str = (
            corrected_local.strftime("%Y-%m-%d %H:%M:%S")
            if corrected_local
            else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        abs_offset_sec = abs(offset_sec) if offset_sec is not None else 0.0

        # 2. 若啟用閾值模式且誤差小於設定秒數 (例如 60 秒)，則略過寫入
        if threshold_seconds is not None and threshold_seconds > 0 and abs_offset_sec < threshold_seconds:
            return {
                "success": True,
                "skipped": True,
                "server": server_name,
                "server_ip": query_result.get("server_ip"),
                "offset_ms": offset_ms,
                "offset_sec": offset_sec,
                "delay_ms": delay_ms,
                "time_str": local_time_str,
                "threshold_sec": threshold_seconds,
                "message": (
                    f"檢測完成：時間偏差為 {abs_offset_sec:.3f} 秒 (小於設定閾值 {threshold_seconds:.0f} 秒)，"
                    f"系統時鐘準確，略過本次寫入。"
                ),
            }

        # 3. 檢查管理員權限
        if not is_admin():
            return {
                "success": False,
                "server": server_name,
                "error": "權限不足：需要【系統管理員權限】才能更新 Windows 系統時鐘。請以管理員身分重新執行程式。",
                "need_admin": True,
                "offset_ms": offset_ms,
                "offset_sec": offset_sec,
                "delay_ms": delay_ms,
                "time_str": local_time_str,
                "skipped": False,
            }

        # 4. 呼叫 Windows API 寫入時間
        write_success = set_windows_time(corrected_utc)
        if not write_success:
            # 若 SetSystemTime 失敗，嘗試備援方案 w32tm
            err_code = ctypes.GetLastError()
            fallback_success = self._fallback_w32tm_sync()
            if not fallback_success:
                return {
                    "success": False,
                    "server": server_name,
                    "error": f"寫入系統時間失敗 (Win32 Error Code: {err_code})",
                    "offset_ms": offset_ms,
                    "offset_sec": offset_sec,
                    "delay_ms": delay_ms,
                    "time_str": local_time_str,
                    "skipped": False,
                }

        msg = (
            f"成功同步時間！時間偏差 {abs_offset_sec:.3f} 秒已超過閾值 ({threshold_seconds:.0f} 秒)，已更新系統時鐘。"
            if (threshold_seconds and threshold_seconds > 0)
            else f"成功同步時間！伺服器: {server_name}，網路延遲: {delay_ms} ms，修正時間誤差: {offset_ms} ms"
        )

        return {
            "success": True,
            "skipped": False,
            "server": server_name,
            "server_ip": query_result.get("server_ip"),
            "offset_ms": offset_ms,
            "offset_sec": offset_sec,
            "delay_ms": delay_ms,
            "time_str": local_time_str,
            "threshold_sec": threshold_seconds,
            "message": msg,
        }

    def _fallback_w32tm_sync(self) -> bool:
        """備援：嘗試呼叫 Windows w32tm 進行同步"""
        try:
            res = subprocess.run(
                ["w32tm", "/resync", "/nowait"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
                if os.name == "nt"
                else 0,
            )
            return res.returncode == 0
        except Exception:
            return False
