using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace WindowsTimeAutoUpdate
{
    static class Program
    {
        [STAThread]
        static void Main(string[] args)
        {
            try
            {
                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                string mainPy = Path.Combine(baseDir, "main.py");

                if (!File.Exists(mainPy))
                {
                    // 若不在同一目錄，嘗試在當前目錄查找
                    mainPy = Path.Combine(Environment.CurrentDirectory, "main.py");
                }

                if (!File.Exists(mainPy))
                {
                    MessageBox.Show(
                        "找不到主程式 main.py！\n請確保 WindowsTimeAutoUpdate.exe 與 main.py 位於相同目錄下。",
                        "Windows 網路自動校時工具",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error
                    );
                    return;
                }

                string pythonw = FindPythonw();
                if (string.IsNullOrEmpty(pythonw))
                {
                    MessageBox.Show(
                        "找不到 Python 執行環境 (pythonw.exe)！\n請確認已安裝 Python 並且加入了系統 PATH。",
                        "Windows 網路自動校時工具",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error
                    );
                    return;
                }

                string arguments = "\"" + mainPy + "\"";
                if (args != null && args.Length > 0)
                {
                    arguments += " " + string.Join(" ", args);
                }

                ProcessStartInfo psi = new ProcessStartInfo
                {
                    FileName = pythonw,
                    Arguments = arguments,
                    WorkingDirectory = Path.GetDirectoryName(mainPy),
                    UseShellExecute = true,
                    Verb = "runas", // 以系統管理員權限啟動
                    WindowStyle = ProcessWindowStyle.Hidden
                };

                Process.Start(psi);
            }
            catch (System.ComponentModel.Win32Exception ex)
            {
                // 使用者在 UAC 提示時選擇「取消/否」
                if (ex.NativeErrorCode != 1223) // 1223 = ERROR_CANCELLED
                {
                    MessageBox.Show("啟動失敗: " + ex.Message, "錯誤", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show("發生未預期的錯誤: " + ex.Message, "錯誤", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        static string FindPythonw()
        {
            // 1. 檢查 PATH
            string pathEnv = Environment.GetEnvironmentVariable("PATH") ?? "";
            string[] paths = pathEnv.Split(';');
            foreach (string p in paths)
            {
                if (string.IsNullOrWhiteSpace(p)) continue;
                try
                {
                    string candidate = Path.Combine(p.Trim(), "pythonw.exe");
                    if (File.Exists(candidate)) return candidate;
                }
                catch { }
            }

            // 2. 檢查常見 Python 安裝路徑
            string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string[] commonLocations = new string[]
            {
                Path.Combine(localAppData, @"Programs\Python\Python314\pythonw.exe"),
                Path.Combine(localAppData, @"Programs\Python\Python313\pythonw.exe"),
                Path.Combine(localAppData, @"Programs\Python\Python312\pythonw.exe"),
                Path.Combine(localAppData, @"Programs\Python\Python311\pythonw.exe"),
                Path.Combine(localAppData, @"Python\pythoncore-3.14-64\pythonw.exe"),
                @"C:\Python314\pythonw.exe",
                @"C:\Python313\pythonw.exe",
                @"C:\Python312\pythonw.exe",
                @"C:\Program Files\Python314\pythonw.exe",
                @"C:\Program Files\Python313\pythonw.exe"
            };

            foreach (string loc in commonLocations)
            {
                if (File.Exists(loc)) return loc;
            }

            // 3. 退回 pythonw 指令名稱
            return "pythonw.exe";
        }
    }
}
