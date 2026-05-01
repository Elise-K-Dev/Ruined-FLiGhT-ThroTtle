using System;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace ThrotleTools
{
    internal static class VJoyTunerLauncher
    {
        [STAThread]
        private static int Main()
        {
            string root = AppDomain.CurrentDomain.BaseDirectory;
            string script = Path.Combine(root, "scripts", "vjoy_tuner.py");

            if (!File.Exists(script))
            {
                MessageBox.Show(
                    "Could not find scripts\\vjoy_tuner.py next to this exe.",
                    "vJoy Tuner",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
                return 1;
            }

            try
            {
                StartPython("pythonw.exe", script, root);
                return 0;
            }
            catch (Win32Exception)
            {
                try
                {
                    StartPython("python.exe", script, root);
                    return 0;
                }
                catch (Exception ex)
                {
                    ShowFailure(ex);
                    return 1;
                }
            }
            catch (Exception ex)
            {
                ShowFailure(ex);
                return 1;
            }
        }

        private static void StartPython(string executable, string script, string workingDirectory)
        {
            using (Process process = new Process())
            {
                process.StartInfo.FileName = executable;
                process.StartInfo.Arguments = "\"" + script + "\"";
                process.StartInfo.WorkingDirectory = workingDirectory;
                process.StartInfo.UseShellExecute = false;
                process.StartInfo.CreateNoWindow = true;
                process.Start();
            }
        }

        private static void ShowFailure(Exception ex)
        {
            MessageBox.Show(
                "Could not start the vJoy tuner." + Environment.NewLine + ex.Message,
                "vJoy Tuner",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }
}
