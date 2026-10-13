"""Exercise launchers with real child processes and legacy Windows decoding."""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == "win32", "Windows launcher regression")
class WindowsLauncherTests(unittest.TestCase):
    def run_launcher(self, doctor_status=0, app_status=0, arguments=()):
        with tempfile.TemporaryDirectory(prefix="air painter ") as temporary:
            project = Path(temporary) / "中文项目"
            project.mkdir()
            shutil.copy2(ROOT / "run_app.py", project / "run_app.py")
            (project / "doctor.py").write_text(f"raise SystemExit({doctor_status})\n", encoding="utf-8")
            (project / "ai_virtual_painter.py").write_text(
                "import json, sys\n"
                "print(json.dumps(sys.argv[1:]), flush=True)\n"
                f"raise SystemExit({app_status})\n", encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(project / "run_app.py"), *arguments],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)

    def test_directory_and_arguments_with_spaces_reach_app(self):
        arguments = ["--settings", "settings with spaces.json", "--no-camera"]
        result = self.run_launcher(arguments=arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.strip(), result.stderr)
        self.assertEqual(json.loads(result.stdout), arguments)

    def test_app_failure_is_returned_to_start_script(self):
        result = self.run_launcher(app_status=7)
        self.assertEqual(result.returncode, 7, result.stderr)

    def test_failed_diagnostics_prevent_app_start(self):
        result = self.run_launcher(doctor_status=3)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_scripts_parse_with_chinese_windows_powershell_encoding(self):
        # Match legacy PowerShell on Chinese Windows, including BOM detection,
        # even when CI's system default encoding is Western or UTF-8.
        command = """
$source = [IO.File]::ReadAllText($env:AIR_PAINTER_SCRIPT_TEST, [Text.Encoding]::GetEncoding(936))
$tokens = $null
$errors = $null
[Management.Automation.Language.Parser]::ParseInput($source, [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count) { $errors | ForEach-Object { Write-Error $_ }; exit 1 }
exit 0
"""
        encoded = base64.b64encode(command.encode("utf-16le")).decode("ascii")
        for filename in ("setup.ps1", "start_windows.ps1"):
            with self.subTest(script=filename):
                environment = dict(os.environ, AIR_PAINTER_SCRIPT_TEST=str(ROOT / filename))
                result = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                    env=environment, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))


if __name__ == "__main__":
    unittest.main()
