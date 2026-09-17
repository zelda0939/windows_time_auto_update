using System;
using System.Diagnostics;
using System.IO;
using System.Security.Principal;
using System.Threading;
using System.Windows.Forms;

namespace WindowsTimeAutoUpdate
{
    static class Program
    {
        [STAThread]
        static void Main(string[] args)
        {
            bool isMinimized = false;
            if (args != null)
            {
                foreach (string a in args)
                {
                    if (string.Equals(a, "--minimized", StringComparison.OrdinalIgnoreCase))
                    {
                        isMinimized = true;
                        break;
                    }
                }
            }

            try
            {
                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                string mainPy = Path.Combine(baseDir, "main.py");

                // 若在雲端硬碟 (Google Drive 等) 開機載入階段，磁碟機可能需要數秒至數十秒掛載
                // 當 main.py 暫不可用時，進行最多 60 秒的重試等待循環
                int waitSeconds = 0;
                int maxWait = isMinimized ? 60 : 3;

                while (!File.Exists(mainPy) && waitSeconds < maxWait)
                {
                    Thread.Sleep(1000);
                    waitSeconds++;

                    if (!File.Exists(mainPy))
                    {
                        mainPy = Path.Combine(Environment.CurrentDirectory, "main.py");
                    }
                }

                if (!File.Exists(mainPy))
                {
                    string err = "找不到主程式 main.py！\n請確保 WindowsTimeAutoUpdate.exe 與 main.py 位於相同目錄下。\n" +
                                 "搜尋路徑：" + baseDir;
                    LogError(err);
                    if (!isMinimized)
                    {
                        MessageBox.Show(
                            err,
                            "Windows 網路自動校時工具",
                            MessageBoxButtons.OK,
                            MessageBoxIcon.Error
                        );
                    }
                    return;
                }

                string pythonw = FindPythonw(baseDir);
                if (string.IsNullOrEmpty(pythonw))
                {
                    string err = "找不到 Python 執行環境 (pythonw.exe)！\n請確認已安裝 Python 或於程式目錄內建 runtime/ 資料夾。";
                    LogError(err);
                    if (!isMinimized)
                    {
                        MessageBox.Show(
                            err,
                            "Windows 網路自動校時工具",
                            MessageBoxButtons.OK,
                            MessageBoxIcon.Error
                        );
                    }
                    return;
                }

                string arguments = "\"" + mainPy + "\"";
                if (args != null && args.Length > 0)
                {
                    arguments += " " + string.Join(" ", args);
                }

                bool alreadyAdmin = IsRunningAsAdmin();

                ProcessStartInfo psi = new ProcessStartInfo
                {
                    FileName = pythonw,
                    Arguments = arguments,
                    WorkingDirectory = Path.GetDirectoryName(mainPy),
                    UseShellExecute = true,
                    // 若已是管理員，或開機背景啟動模式 (--minimized)，不強制彈 UAC 視窗以防 Windows 阻擋
                    Verb = (alreadyAdmin || isMinimized) ? "" : "runas",
                    WindowStyle = ProcessWindowStyle.Hidden
                };

                Process.Start(psi);
            }
            catch (System.ComponentModel.Win32Exception ex)
            {
                // 使用者在 UAC 提示時選擇「取消/否」
                if (ex.NativeErrorCode != 1223) // 1223 = ERROR_CANCELLED
                {
                    LogError("啟動失敗 (Win32Exception): " + ex.Message);
                    if (!isMinimized)
                    {
                        MessageBox.Show("啟動失敗: " + ex.Message, "錯誤", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    }
                }
            }
            catch (Exception ex)
            {
                LogError("發生未預期的錯誤: " + ex.Message + "\n" + ex.StackTrace);
                if (!isMinimized)
                {
                    MessageBox.Show("發生未預期的錯誤: " + ex.Message, "錯誤", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
        }

        static bool IsRunningAsAdmin()
        {
            try
            {
                WindowsIdentity identity = WindowsIdentity.GetCurrent();
                WindowsPrincipal principal = new WindowsPrincipal(identity);
                return principal.IsInRole(WindowsBuiltInRole.Administrator);
            }
            catch
            {
                return false;
            }
        }

        static void LogError(string message)
        {
            try
            {
                string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                string logDir = Path.Combine(localAppData, "WindowsTimeAutoUpdate");
                if (!Directory.Exists(logDir))
                {
                    Directory.CreateDirectory(logDir);
                }
                string logFile = Path.Combine(logDir, "launcher_error.log");
                string logText = string.Format("[{0:yyyy-MM-dd HH:mm:ss}] {1}\r\n", DateTime.Now, message);
                File.AppendAllText(logFile, logText);
            }
            catch { }
        }

        static string FindPythonw(string baseDir)
        {
            // 0. 第一優先：檢查本程式同目錄下之免安裝便攜 Runtime (runtime\\pythonw.exe 或 python\\pythonw.exe)
            if (!string.IsNullOrEmpty(baseDir))
            {
                string localRuntime = Path.Combine(baseDir, "runtime", "pythonw.exe");
                if (File.Exists(localRuntime)) return localRuntime;

                string localPythonDir = Path.Combine(baseDir, "python", "pythonw.exe");
                if (File.Exists(localPythonDir)) return localPythonDir;
            }

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
                Path.Combine(localAppData, @"Python\pythoncore-3.14-64\pythonw.exe"),
                Path.Combine(localAppData, @"Programs\Python\Python314\pythonw.exe"),
                Path.Combine(localAppData, @"Programs\Python\Python313\pythonw.exe"),
                Path.Combine(localAppData, @"Programs\Python\Python312\pythonw.exe"),
                Path.Combine(localAppData, @"Programs\Python\Python311\pythonw.exe"),
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
