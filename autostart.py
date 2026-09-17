"""
Windows 開機自動啟動與本機部署管理模組 (autostart.py)
為徹底解決 Google Drive 雲端硬碟 (G: 槽) 開機登入時尚未連線掛載、中文路徑編碼受損、
以及開機 UAC 提權被 Windows 系統阻擋等問題，本模組採用「本機 LocalAppData 永久部署 +
Windows 工作排程器 (Task Scheduler) 最高權限免 UAC 靜默常駐」的終極架構。
"""

import os
import shutil
import subprocess
import sys
import winreg
from typing import Dict, List, Optional, Tuple

TASK_NAME = "WindowsTimeAutoUpdate_Startup"
REG_RUN_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_KEY = "WindowsTimeAutoUpdate"

DEPLOY_FILES = [
    "WindowsTimeAutoUpdate.exe",
    "main.py",
    "gui.py",
    "ntp_client.py",
    "time_syncer.py",
    "scheduler.py",
    "config_manager.py",
    "autostart.py",
    "tray_icon.py",
    "config.json",
    "app_icon.ico",
]


def get_local_appdata_dir() -> str:
    """取得本機 LocalAppData 的專屬安裝路徑 (位於 C 槽純 ASCII 路徑，開機秒讀取)"""
    local_app_data = os.environ.get(
        "LOCALAPPDATA",
        os.path.join(os.path.expanduser("~"), "AppData", "Local"),
    )
    target_dir = os.path.join(local_app_data, "WindowsTimeAutoUpdate")
    os.makedirs(target_dir, exist_ok=True)
    return target_dir


def deploy_to_local_appdata() -> Tuple[bool, str]:
    """
    將程式核心檔案同步安裝/部署至本機 LocalAppData 目錄
    確保開機時在 Google Drive 尚未掛載的情況下也能 100% 正常自動常駐運行
    :return: (是否成功, 部署目錄路徑)
    """
    try:
        source_dir = os.path.dirname(os.path.abspath(__file__))
        dest_dir = get_local_appdata_dir()

        for fname in DEPLOY_FILES:
            src = os.path.join(source_dir, fname)
            dst = os.path.join(dest_dir, fname)
            if os.path.exists(src):
                # 若為設定檔且目的地已有設定，可選擇保留或複製
                try:
                    shutil.copy2(src, dst)
                except Exception as e:
                    print(f"複製 {fname} 警告: {e}")

        # 若專案內建免安裝便攜 runtime/ 目錄，亦同步部署至 LocalAppData 以供未安裝 Python 之電腦開機自啟動
        src_runtime = os.path.join(source_dir, "runtime")
        dst_runtime = os.path.join(dest_dir, "runtime")
        if os.path.exists(src_runtime):
            # 若目的地尚未有完整的 runtime/pythonw.exe，進行複製
            if not os.path.exists(os.path.join(dst_runtime, "pythonw.exe")):
                try:
                    shutil.copytree(
                        src_runtime,
                        dst_runtime,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                        dirs_exist_ok=True,
                    )
                except Exception as e:
                    print(f"同步 runtime 警告: {e}")

        return True, dest_dir
    except Exception as e:
        print(f"部署至 LocalAppData 失敗: {e}")
        return False, ""


def get_application_executable(prefer_local: bool = True) -> Tuple[str, str]:
    """
    取得啟動本程式所需的主執行檔路徑與參數設定
    :param prefer_local: 是否優先使用本機 LocalAppData 目錄中的執行檔 (推薦開機時使用)
    :return: (可執行檔絕對路徑, 啟動參數字串)
    """
    # 1. 優先檢查本機 LocalAppData 目錄中的 WindowsTimeAutoUpdate.exe
    if prefer_local:
        local_dir = get_local_appdata_dir()
        local_exe = os.path.join(local_dir, "WindowsTimeAutoUpdate.exe")
        if os.path.exists(local_exe):
            return local_exe, ""

    # 2. 檢查當前專案目錄下的 WindowsTimeAutoUpdate.exe
    base_dir = os.path.dirname(os.path.abspath(__file__))
    exe_launcher = os.path.join(base_dir, "WindowsTimeAutoUpdate.exe")
    if os.path.exists(exe_launcher):
        return exe_launcher, ""

    # 3. 若為 PyInstaller 打包後的 exe
    if getattr(sys, "frozen", False):
        return os.path.abspath(sys.executable), ""

    # 4. 腳本模式，使用 pythonw.exe
    py_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(py_dir, "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable

    main_script = os.path.join(base_dir, "main.py")
    return pythonw, f'"{main_script}"'


def get_launch_command(start_minimized: bool = True, prefer_local: bool = True) -> str:
    """
    建構開機時執行的完整命令字串
    :param start_minimized: 是否加上 --minimized 參數
    :param prefer_local: 是否優先指向本機 LocalAppData
    :return: 命令字串
    """
    executable, args_prefix = get_application_executable(prefer_local=prefer_local)
    extra_arg = "--minimized" if start_minimized else ""

    parts = [f'"{executable}"']
    if args_prefix:
        parts.append(args_prefix)
    if extra_arg:
        parts.append(extra_arg)

    return " ".join(parts)


def is_task_scheduler_enabled() -> bool:
    """檢查 Windows 工作排程器中是否已存在本工具之開機工作"""
    try:
        cmd = f'schtasks /query /tn "{TASK_NAME}"'
        res = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return res.returncode == 0
    except Exception:
        return False


def is_registry_autostart_enabled() -> bool:
    """檢查目前登錄檔 (HKCU Run) 中是否已啟用開機自動啟動"""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_RUN_PATH, 0, winreg.KEY_READ
        ) as key:
            value, _ = winreg.QueryValueEx(key, APP_REG_KEY)
            return bool(value)
    except FileNotFoundError:
        return False
    except Exception:
        return False


def is_autostart_enabled() -> bool:
    """檢查是否已啟用任何形式的開機自動啟動 (排程器或登錄檔)"""
    return is_task_scheduler_enabled() or is_registry_autostart_enabled()


def check_autostart_status() -> Dict[str, any]:
    """取得開機自啟動詳細狀態診斷資訊"""
    task_enabled = is_task_scheduler_enabled()
    reg_enabled = is_registry_autostart_enabled()

    reg_command = None
    if reg_enabled:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, REG_RUN_PATH, 0, winreg.KEY_READ
            ) as key:
                reg_command, _ = winreg.QueryValueEx(key, APP_REG_KEY)
        except Exception:
            pass

    executable, _ = get_application_executable(prefer_local=True)
    exe_exists = os.path.exists(executable)
    local_dir = get_local_appdata_dir()

    return {
        "enabled": task_enabled or reg_enabled,
        "mode": "task_scheduler" if task_enabled else ("registry" if reg_enabled else "none"),
        "task_scheduler_enabled": task_enabled,
        "registry_enabled": reg_enabled,
        "registry_command": reg_command,
        "target_executable": executable,
        "target_exists": exe_exists,
        "local_deployed_dir": local_dir,
    }


def clean_corrupted_registry_entries():
    """清除登錄檔中可能殘留的舊有或損壞項目"""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_RUN_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            try:
                winreg.DeleteValue(key, APP_REG_KEY)
            except FileNotFoundError:
                pass
    except Exception:
        pass


def set_task_scheduler_autostart(enable: bool, start_minimized: bool = True) -> bool:
    """
    透過 Windows 工作排程器 (schtasks) 建立或刪除最高權限免 UAC 開機啟動工作
    :param enable: True 為建立，False 為刪除
    :param start_minimized: 是否最小化啟動
    :return: 是否成功
    """
    if enable:
        # 自動先同步部署至本機 LocalAppData 目錄
        deploy_to_local_appdata()

        cmd_str = get_launch_command(start_minimized=start_minimized, prefer_local=True)
        # 建立排程工作：登入時觸發 (/sc ONLOGON)、最高權限 (/rl HIGHEST)
        sch_cmd = f'schtasks /create /f /tn "{TASK_NAME}" /tr "{cmd_str}" /sc ONLOGON /rl HIGHEST'
        res = subprocess.run(
            sch_cmd,
            shell=True,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return res.returncode == 0
    else:
        sch_cmd = f'schtasks /delete /f /tn "{TASK_NAME}"'
        res = subprocess.run(
            sch_cmd,
            shell=True,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return res.returncode == 0 or not is_task_scheduler_enabled()


def set_registry_autostart(enable: bool, start_minimized: bool = True) -> bool:
    """
    透過 Windows 登錄檔 (HKCU Run) 設定或解除開機啟動 (備援模式)
    :param enable: True 為啟用，False 為停用
    :param start_minimized: 是否最小化啟動
    :return: 是否成功
    """
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_RUN_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enable:
                deploy_to_local_appdata()
                cmd = get_launch_command(start_minimized=start_minimized, prefer_local=True)
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


def set_autostart(enable: bool, start_minimized: bool = True) -> bool:
    """
    綜合設定開機自動啟動 (優先使用本機 LocalAppData + 免 UAC 工作排程器)
    :param enable: True 為啟用，False 為停用
    :param start_minimized: 是否最小化啟動
    :return: 是否成功
    """
    if enable:
        # 清除過往可能衝突的舊登錄檔項目
        clean_corrupted_registry_entries()

        # 優先嘗試工作排程器 (以最高管理員權限靜默開機常駐，免 UAC)
        task_success = set_task_scheduler_autostart(True, start_minimized)
        if task_success:
            return True

        # 若排程器建立失敗（例如非管理員無權限），降級使用本機登錄檔
        return set_registry_autostart(True, start_minimized)
    else:
        # 停用時兩者一併清除
        task_ok = set_task_scheduler_autostart(False)
        reg_ok = set_registry_autostart(False)
        return task_ok and reg_ok


def install_and_setup_autostart():
    """CLI / 批次檔調用：自動執行本機部署並註冊開機工作排程"""
    print("[*] Deploying application to LocalAppData...")
    ok, dest = deploy_to_local_appdata()
    if ok:
        print(f"[+] Deployed successfully to: {dest}")
    else:
        print("[-] Deployment warning.")

    print("[*] Registering Task Scheduler autostart...")
    res = set_autostart(True, start_minimized=True)
    if res:
        print("[+] Autostart task created successfully!")
    else:
        print("[-] Failed to create autostart task.")

    status = check_autostart_status()
    print("[*] Status:")
    print(f"    Mode: {status.get('mode')}")
    print(f"    Task Scheduler: {status.get('task_scheduler_enabled')}")
    print(f"    Target: {status.get('target_executable')}")
    print(f"    Ready: {status.get('target_exists')}")


if __name__ == "__main__":
    install_and_setup_autostart()
