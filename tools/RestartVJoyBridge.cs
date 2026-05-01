using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace ThrotleTools
{
    internal static class RestartVJoyBridge
    {
        [STAThread]
        private static int Main()
        {
            string root = AppDomain.CurrentDomain.BaseDirectory;
            string scripts = Path.Combine(root, "scripts");
            string stopScript = Path.Combine(scripts, "stop-vjoy-bridge.ps1");
            string startScript = Path.Combine(scripts, "start-vjoy-bridge.ps1");

            if (!File.Exists(stopScript) || !File.Exists(startScript))
            {
                MessageBox.Show(
                    "Could not find bridge scripts next to this exe.",
                    "vJoy Bridge",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
                return 1;
            }

            try
            {
                RunPowerShell(stopScript, root);
                RunPowerShell(startScript, root);
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    ex.Message,
                    "vJoy Bridge Restart Failed",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
                return 1;
            }

            MessageBox.Show(
                "vJoy bridge restarted.",
                "vJoy Bridge",
                MessageBoxButtons.OK,
                MessageBoxIcon.Information);
            return 0;
        }

        private static void RunPowerShell(string scriptPath, string workingDirectory)
        {
            using (Process process = new Process())
            {
                process.StartInfo.FileName = "powershell.exe";
                process.StartInfo.Arguments =
                    "-NoProfile -ExecutionPolicy Bypass -File \"" + scriptPath + "\"";
                process.StartInfo.WorkingDirectory = workingDirectory;
                process.StartInfo.UseShellExecute = false;
                process.StartInfo.CreateNoWindow = true;
                process.StartInfo.RedirectStandardOutput = true;
                process.StartInfo.RedirectStandardError = true;

                process.Start();
                string output = process.StandardOutput.ReadToEnd();
                string error = process.StandardError.ReadToEnd();
                process.WaitForExit();

                if (process.ExitCode != 0)
                {
                    throw new InvalidOperationException(
                        "Command failed: " + Path.GetFileName(scriptPath) + Environment.NewLine +
                        output + Environment.NewLine + error);
                }
            }
        }
    }
}
