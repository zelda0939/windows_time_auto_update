"""
Windows 網路自動校時工具打包腳本 (build.py)
透過 PyInstaller 將專案打包為免安裝獨立發行包 (dist/WindowsTimeAutoUpdate/WindowsTimeAutoUpdate.exe)
"""

import os
import shutil
import subprocess
import sys

def main():
    print("=" * 60)
    print("Windows 網路自動校時工具 - 免安裝獨立發行包打包程序")
    print("=" * 60)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    # 1. 檢查並更新打包依賴
    print("\n[1/3] 正在檢查並更新打包必備套件 (PyInstaller, Pillow, pystray)...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "--upgrade",
            "pyinstaller", "Pillow", "pystray"
        ])
    except subprocess.CalledProcessError as e:
        print(f"[-] 安裝套件失敗: {e}")
        input("\n請按 Enter 鍵結束...")
        sys.exit(1)

    # 2. 執行 PyInstaller 打包 (採用相容性最佳的 onedir 目錄模式，避免 Python 3.14 的 bootloader PKG 錯誤)
    print("\n[2/3] 正在編譯打包為免安裝獨立發行版本...")
    main_py = os.path.join(base_dir, "main.py")
    dist_dir = os.path.join(base_dir, "dist")
    target_dir = os.path.join(dist_dir, "WindowsTimeAutoUpdate")
    
    # 清理舊輸出
    if os.path.exists(target_dir):
        try:
            shutil.rmtree(target_dir)
        except Exception:
            pass

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--onedir",
        "--name=WindowsTimeAutoUpdate",
        "--clean",
        main_py
    ]
    
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        print(f"\n[-] 打包過程發生錯誤: {e}")
        input("\n請按 Enter 鍵結束...")
        sys.exit(1)

    # 3. 完成提示
    exe_path = os.path.join(target_dir, "WindowsTimeAutoUpdate.exe")
    print("\n" + "=" * 60)
    if os.path.exists(exe_path):
        print("打包成功！")
        print(f"免安裝獨立目錄: {target_dir}")
        print(f"主執行檔: {exe_path}")
        print("\n提示：您可以將整个 [WindowsTimeAutoUpdate] 資料夾複製到任何 Windows 電腦上使用 (免安裝 Python)。")
    else:
        print("打包已完成，請查看 dist 資料夾。")
    print("=" * 60)
    
    input("\n請按 Enter 鍵結束...")

if __name__ == "__main__":
    main()
