"""The legacy workflow must never compete with connected Metricool publishing."""
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
