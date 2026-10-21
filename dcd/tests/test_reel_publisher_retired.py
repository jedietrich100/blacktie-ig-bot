"""The legacy workflow must never compete with connected Metricool publishing."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest


class LegacyWorkflowRetirementTests(unittest.TestCase):
    def test_legacy_workflow_has_no_scheduled_or_live_publish_path(self):
        path = Path(__file__).resolve().parents[2] / ".github/workflows/digital-calm-daily-reel.yml"
        workflow = path.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch: {}", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("cron:", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertNotIn("publish_daily_reel.py", workflow)
        self.assertNotIn("publish_buffer", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertIn("cannot publish", workflow)

    def test_old_workflow_gate_cannot_reenable_buffer(self):
        script = Path(__file__).resolve().parents[1] / "publish_daily_reel.py"
        for event in ("schedule", "workflow_dispatch"):
            with self.subTest(event=event), tempfile.TemporaryDirectory() as folder:
                output = Path(folder) / "output"
                env = dict(os.environ, GITHUB_EVENT_NAME=event, GITHUB_OUTPUT=str(output))
                result = subprocess.run([sys.executable, str(script), "--check-schedule"],
                                        env=env, text=True, capture_output=True, check=True)
                self.assertIn("run=false\n", output.read_text())
                self.assertIn("retired", result.stdout)

    def test_direct_legacy_cli_refuses_before_credentials_or_network(self):
        script = Path(__file__).resolve().parents[1] / "publish_daily_reel.py"
        env = dict(os.environ, GITHUB_EVENT_NAME="workflow_dispatch", DCD_BUFFER_API_KEY="")
        result = subprocess.run([sys.executable, str(script)], env=env, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("retired; no submission made", result.stderr)


if __name__ == "__main__":
    unittest.main()

