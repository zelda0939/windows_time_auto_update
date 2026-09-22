"""
Windows 網路自動校時工具 - 免安裝綠色便攜包建置腳本 (create_portable_package.py)
功能：
1. 從當前 Python 環境提取極致精簡的獨立 Python Runtime (約 50~60MB)
2. 包含 Tkinter、Pillow、pystray 等完整依賴，無多餘套件
3. 自動進行 Runtime 完整性與模組載入自我驗證
4. 支援一鍵將整個程式打包為 WindowsTimeAutoUpdate_Portable.zip
"""

import os
import shutil
import subprocess
import sys
import zipfile

def copy_file_safe(src: str, dst: str):
    if os.path.exists(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)

def copy_tree_filtered(src_dir: str, dst_dir: str, exclude_dirs=None, exclude_exts=None):
    if not os.path.exists(src_dir):
        return
    if exclude_dirs is None:
        exclude_dirs = {"__pycache__", "test", "tests", "idlelib"}
    if exclude_exts is None:
        exclude_exts = {".pyc", ".pyo", ".pdb"}

    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        rel_path = os.path.relpath(root, src_dir)
        target_sub = os.path.join(dst_dir, rel_path)
        os.makedirs(target_sub, exist_ok=True)

        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in exclude_exts:
                continue
            src_file = os.path.join(root, f)
            dst_file = os.path.join(target_sub, f)
            try:
                shutil.copy2(src_file, dst_file)
            except Exception as e:
                print(f"  [!] 複製 {f} 略過或警告: {e}")

def build_runtime(target_runtime_dir: str):
    print(f"[*] 正在從目前環境提取獨立精簡 Python 執行時環境至: {target_runtime_dir} ...")
    prefix = sys.prefix

    if os.path.exists(target_runtime_dir):
        print("  [-] 發現既有 runtime 資料夾，正在進行清理...")
        shutil.rmtree(target_runtime_dir, ignore_errors=True)
    os.makedirs(target_runtime_dir, exist_ok=True)

    # 1. 複製核心執行檔與 DLL
    core_files = [
        "python.exe", "pythonw.exe", "python3.dll", "python314.dll",
        "vcruntime140.dll", "vcruntime140_1.dll"
    ]
    # 也複製任何 python3*.dll
    for item in os.listdir(prefix):
        if item.lower().startswith("python3") and item.lower().endswith(".dll"):
            if item not in core_files:
                core_files.append(item)

    for cf in core_files:
        src = os.path.join(prefix, cf)
        dst = os.path.join(target_runtime_dir, cf)
        copy_file_safe(src, dst)

    # 2. 複製 DLLs 目錄
    src_dlls = os.path.join(prefix, "DLLs")
    dst_dlls = os.path.join(target_runtime_dir, "DLLs")
    if os.path.exists(src_dlls):
        print("  [*] 正在複製 DLLs 二進位擴充組件 (含 Tkinter、ctypes)...")
        copy_tree_filtered(src_dlls, dst_dlls)

    # 3. 複製 tcl 資源目錄 (Tkinter 必要)
    src_tcl = os.path.join(prefix, "tcl")
    dst_tcl = os.path.join(target_runtime_dir, "tcl")
    if os.path.exists(src_tcl):
        print("  [*] 正在複製 tcl/tk GUI 資源組件...")
        copy_tree_filtered(src_tcl, dst_tcl)

    # 4. 複製標準函式庫 (排除未使用的除錯與測試模組)
    src_lib = os.path.join(prefix, "Lib")
    dst_lib = os.path.join(target_runtime_dir, "Lib")
    print("  [*] 正在複製 Python 標準函式庫...")
    
    # 複製標準庫檔案與目錄 (排除 site-packages)
    for item in os.listdir(src_lib):
        if item == "site-packages":
            continue
        if item in {"test", "tests", "idlelib", "distutils", "ensurepip", "venv"}:
            continue
        item_src = os.path.join(src_lib, item)
        item_dst = os.path.join(dst_lib, item)
        if os.path.isfile(item_src):
            copy_file_safe(item_src, item_dst)
        else:
            copy_tree_filtered(item_src, item_dst)

    # 5. 只精選複製需要的 site-packages (PIL, pystray, six.py)
    src_sp = os.path.join(src_lib, "site-packages")
    dst_sp = os.path.join(dst_lib, "site-packages")
    os.makedirs(dst_sp, exist_ok=True)

    target_items = ["PIL", "pystray", "six.py"]
    print("  [*] 正在複製必要第三方套件 (PIL, pystray, six.py)...")
    for item in target_items:
        p_src = os.path.join(src_sp, item)
        p_dst = os.path.join(dst_sp, item)
        if os.path.exists(p_src):
            if os.path.isfile(p_src):
                copy_file_safe(p_src, p_dst)
            else:
                copy_tree_filtered(p_src, p_dst)
        else:
            print(f"  [!] 找不到套件項目: {p_src}")

    # 複製可能關聯的 dist-info
    for item in os.listdir(src_sp):
        item_lower = item.lower()
        if any(item_lower.startswith(p.lower()) and "dist-info" in item_lower for p in ["pillow", "pystray", "six"]):
            copy_tree_filtered(os.path.join(src_sp, item), os.path.join(dst_sp, item))

    print("[+] 獨立 Runtime 複製完成！")

def verify_runtime(target_runtime_dir: str) -> bool:
    print("\n[*] 正在驗證獨立 Runtime 是否可在零依賴環境下自主運行...")
    py_exec = os.path.join(target_runtime_dir, "python.exe")
    if not os.path.exists(py_exec):
        print(f"[-] 找不到執行檔: {py_exec}")
        return False

    verify_code = (
        "import sys, os\n"
        "print('  Python Version:', sys.version.split()[0])\n"
        "import tkinter; print('  [OK] tkinter 模組載入正常')\n"
        "import ctypes; print('  [OK] ctypes 模組載入正常')\n"
        "import socket; print('  [OK] socket 模組載入正常')\n"
        "import json; print('  [OK] json 模組載入正常')\n"
        "import PIL; print('  [OK] Pillow (PIL) 模組載入正常')\n"
        "import pystray; print('  [OK] pystray 系統匣模組載入正常')\n"
        "print('ALL_DEPENDENCIES_VERIFIED_SUCCESSFULLY')\n"
    )

    env = os.environ.copy()
    # 清空外部 PYTHONHOME 與 PYTHONPATH，確保完全使用內建 runtime
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)

    try:
        res = subprocess.run(
            [py_exec, "-c", verify_code],
            capture_output=True,
            text=True,
            env=env,
            timeout=15
        )
        print(res.stdout)
        if "ALL_DEPENDENCIES_VERIFIED_SUCCESSFULLY" in res.stdout:
            print("[+] 恭喜！獨立 Runtime 驗證 100% 通過！")
            return True
        else:
            print(f"[-] 驗證失敗，錯誤輸出:\n{res.stderr}")
            return False
    except Exception as e:
        print(f"[-] 驗證過程發生異常: {e}")
        return False

def create_portable_zip(base_dir: str, zip_output_path: str):
    print(f"\n[*] 正在封裝免安裝綠色便攜壓縮檔: {os.path.basename(zip_output_path)} ...")
    include_files = [
        "WindowsTimeAutoUpdate.exe",
        "main.py",
        "gui.py",
        "ntp_client.py",
        "http_time_client.py",
        "time_syncer.py",
        "scheduler.py",
        "config_manager.py",
        "autostart.py",
        "tray_icon.py",
        "config.json",
        "app_icon.ico",
        "create_desktop_shortcut.bat",
        "README.md",
    ]

    with zipfile.ZipFile(zip_output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # 加入程式本體檔案
        for f in include_files:
            fp = os.path.join(base_dir, f)
            if os.path.exists(fp):
                zf.write(fp, arcname=f)
                print(f"  加入: {f}")

        # 加入 runtime 資料夾
        runtime_dir = os.path.join(base_dir, "runtime")
        if os.path.exists(runtime_dir):
            print("  加入 runtime/ 目錄 (此步驟可能需要數秒鐘)...")
            for root, dirs, files in os.walk(runtime_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, base_dir)
                    zf.write(full_path, arcname=rel_path)

    zip_size_mb = os.path.getsize(zip_output_path) / 1024 / 1024
    print(f"[+] 綠色免安裝便攜包建立成功！大小約: {zip_size_mb:.2f} MB")
    print(f"[+] 檔案路徑: {zip_output_path}")

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)
    runtime_dir = os.path.join(base_dir, "runtime")

    print("=" * 65)
    print("Windows 網路自動校時工具 - 建立免安裝綠色便攜環境")
    print("=" * 65)

    build_runtime(runtime_dir)
    if verify_runtime(runtime_dir):
        zip_path = os.path.join(base_dir, "WindowsTimeAutoUpdate_Portable.zip")
        create_portable_zip(base_dir, zip_path)
        print("\n" + "=" * 65)
        print("【完成】您可以直接將專案資料夾（含 runtime/）或")
        print(f"【壓縮包】{os.path.basename(zip_path)}")
        print("複製到任何未安裝 Python 的 Windows 電腦上，雙擊即可直接運行！")
        print("=" * 65)
    else:
        print("\n[-] 獨立 Runtime 驗證未通過，請檢查錯誤訊息。")

if __name__ == "__main__":
    main()
