import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class ScheduleTests(unittest.TestCase):
    def gate(self, event, cron='', enabled='true', manual='false', offset='-0500', day='2026-10-01'):
        workflow = Path(__file__).resolve().parents[1] / '.github/workflows/circus-peanuts-daily.yml'
        text = workflow.read_text()
        start = text.index('          set -euo pipefail')
        end = text.index('      - uses: actions/checkout@v4', start)
        script = '\n'.join(line[10:] for line in text[start:end].splitlines())
        prefix = 'date() { if [ "$1" = "+%z" ]; then echo "$TEST_OFFSET"; else echo "$TEST_DAY"; fi; }\n'
        with tempfile.NamedTemporaryFile() as out:
            env = dict(os.environ, EVENT=event, CRON=cron, ENABLED=enabled, MANUAL_PUBLISH=manual,
                TEST_OFFSET=offset, TEST_DAY=day, GITHUB_OUTPUT=out.name)
            subprocess.run(['bash', '-c', prefix + script], env=env, check=True, capture_output=True)
            return dict(line.split('=', 1) for line in Path(out.name).read_text().splitlines())

    def test_summer_noon_only(self):
        self.assertEqual(self.gate('schedule', '0 17 * * *')['publish'], 'true')
        self.assertEqual(self.gate('schedule', '0 18 * * *')['publish'], 'false')

    def test_winter_noon_only(self):
        self.assertEqual(self.gate('schedule', '0 18 * * *', offset='-0600')['publish'], 'true')
        self.assertEqual(self.gate('schedule', '0 17 * * *', offset='-0600')['publish'], 'false')

    def test_disabled(self):
        for event in ('schedule', 'push', 'workflow_dispatch'):
            self.assertEqual(self.gate(event, '0 17 * * *', enabled='false', manual='true')['publish'], 'false')

    def test_manual_preview_and_publish(self):
        self.assertEqual(self.gate('workflow_dispatch')['publish'], 'false')
        self.assertEqual(self.gate('workflow_dispatch', manual='true')['publish'], 'true')

    def test_launch_date_only(self):
        self.assertEqual(self.gate('push')['publish'], 'true')
        self.assertEqual(self.gate('push', day='2026-10-02')['publish'], 'false')

    def test_unrecognized_event_fails_closed(self):
        self.assertEqual(self.gate('pull_request')['publish'], 'false')

if __name__ == '__main__':
    unittest.main()
