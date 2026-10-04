"""Offline regressions: no credentials, HTTP requests, rendering, or git pushes."""
import copy
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('circus_daily', ROOT / 'circus/publish_daily.py')
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)
ZONE = publisher.ZONE


def local(value):
    return dt.datetime.fromisoformat(value).replace(tzinfo=ZONE)


def cron_times(cron):
    minutes, hours, *_ = cron.split()
    utc_hours = range(int(hours.split('-')[0]), int(hours.split('-')[1]) + 1) if '-' in hours else map(int, hours.split(','))
    return [(hour, int(minute)) for hour in utc_hours for minute in minutes.split(',')]


class ScheduleTests(unittest.TestCase):
    def test_primary_and_backups_for_both_offsets(self):
        for day, offset in [('2026-10-04', -5), ('2026-12-04', -6)]:
            for clock in ['12:00', '12:17', '12:37', '13:17', '13:37', '13:59:59']:
                for cron in publisher.SCHEDULES[offset]:
                    with self.subTest(day=day, clock=clock, cron=cron):
                        self.assertIsNone(publisher.schedule_skip_reason(local(day + 'T' + clock), cron))

    def test_window_boundaries_and_severely_delayed_start(self):
        for day, offset in [('2026-10-04', -5), ('2026-12-04', -6)]:
            for clock in ['00:00', '11:59:59', '14:00', '15:33', '23:59']:
                for cron in publisher.SCHEDULES[offset]:
                    with self.subTest(day=day, clock=clock, cron=cron):
                        self.assertEqual(publisher.schedule_skip_reason(local(day + 'T' + clock), cron),
                                         'Skipping outside noon publishing window')

    def test_inactive_and_unknown_crons_are_rejected(self):
        for day, active, inactive in [('2026-10-04', -5, -6), ('2026-12-04', -6, -5)]:
            for cron in (publisher.SCHEDULES[inactive] - publisher.SCHEDULES[active]) | {'', '*/5 * * * *'}:
                self.assertEqual(publisher.schedule_skip_reason(local(day + 'T12:17'), cron),
                                 'Skipping alternate daylight-saving cron slot')

    def test_daylight_saving_transition_dates(self):
        for day, expected in [('2026-03-07', -6), ('2026-03-08', -5),
                              ('2026-10-31', -5), ('2026-11-01', -6)]:
            for offset, crons in publisher.SCHEDULES.items():
                for cron in crons:
                    with self.subTest(day=day, cron=cron):
                        self.assertEqual(publisher.schedule_skip_reason(local(day + 'T12:17'), cron) is None,
                                         cron in publisher.SCHEDULES[expected])

    def test_utc_times_use_chicago_and_reject_wrong_date(self):
        self.assertTrue(publisher.noon_window_open(dt.datetime(2026, 10, 4, 17, tzinfo=dt.timezone.utc), '2026-10-04'))
        self.assertTrue(publisher.noon_window_open(dt.datetime(2026, 12, 4, 18, tzinfo=dt.timezone.utc), '2026-12-04'))
        self.assertFalse(publisher.noon_window_open(local('2026-10-05T12:17'), '2026-10-04'))

    def test_workflow_crons_and_safety_settings(self):
        workflow = (ROOT / '.github/workflows/circus-peanuts-daily.yml').read_text()
        self.assertEqual(set(re.findall(r"cron: '([^']+)'", workflow)), set.union(*publisher.SCHEDULES.values()))
        self.assertNotRegex(workflow, r'^  push:', 'Workflow edits must not publish')
        self.assertNotIn('\n  push:', workflow)
        self.assertIn('workflow_dispatch: {}', workflow)
        self.assertIn('group: circus-peanuts-daily', workflow)
        self.assertIn('cancel-in-progress: false', workflow)
        self.assertIn('ref: main', workflow)
        self.assertIn('fetch-depth: 0', workflow)
        self.assertIn('python -m unittest discover -s circus/tests -v', workflow)

    def test_each_offset_schedules_exactly_the_five_intended_attempts(self):
        for offset in [-5, -6]:
            times = []
            for cron in publisher.SCHEDULES[offset]:
                times.extend((hour + offset, minute) for hour, minute in cron_times(cron)
                             if 12 <= hour + offset < 14)
            self.assertEqual(sorted(times), [(12, 0), (12, 17), (12, 37), (13, 17), (13, 37)])

    def test_cron_expressions_never_fire_simultaneously(self):
        crons = set.union(*publisher.SCHEDULES.values())
        times = [when for cron in crons for when in cron_times(cron)]
        self.assertEqual(len(times), len(set(times)))


class PublishSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ledger = Path(self.temp.name) / 'ledger.json'
        self.event = Path(self.temp.name) / 'event.json'
        self.event.write_text(json.dumps({'schedule': '17,37 17-19 * * *'}))
        self.now = local('2026-10-04T12:17')
        self.rows = []
        self.calls = []
        self.saved = []
        self.publish_error = False
        self.cutoff_during_processing = False
        self.cutoff_during_reservation = False
        owner = self

        class Clock(dt.datetime):
            @staticmethod
            def now(zone):
                return owner.now.astimezone(zone)

        self.start_patch(patch.object(publisher, 'dt', SimpleNamespace(datetime=Clock)))
        self.start_patch(patch.object(publisher, 'LEDGER', self.ledger))
        self.start_patch(patch.dict(os.environ, {
            'GITHUB_EVENT_NAME': 'schedule', 'GITHUB_EVENT_PATH': str(self.event),
            'GITHUB_REPOSITORY': 'example/test', 'CIRCUS_IG_ACCESS_TOKEN': 'fake-test-token',
            'CIRCUS_IG_USER_ID': '123',
        }, clear=True))
        self.start_patch(patch.object(publisher, 'api', side_effect=self.fake_api))
        self.start_patch(patch.object(publisher, 'persist', side_effect=self.persist))
        self.render = self.start_patch(patch.object(publisher, 'render'))
        self.git = self.start_patch(patch.object(publisher, 'git', return_value='fake-image-commit'))
        self.start_patch(patch.object(publisher.requests, 'get', return_value=SimpleNamespace(ok=True, content=b'\xff\xd8\xff')))
        self.start_patch(patch.object(publisher.requests, 'request', side_effect=AssertionError('Real HTTP is forbidden')))
        self.start_patch(patch.object(publisher.time, 'sleep'))

    def start_patch(self, patcher):
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def persist(self, ledger, message, extra=()):
        self.ledger.write_text(json.dumps(ledger))
        self.saved.append((message, copy.deepcopy(ledger)))
        if self.cutoff_during_reservation and message.startswith('Circus: reserve publication'):
            self.now = local('2026-10-04T14:00')

    def fake_api(self, method, path, token, **kwargs):
        self.calls.append((method, path))
        if (method, path) == ('GET', 'me'):
            return {'username': 'circuspeanutsdaily', 'user_id': '123'}
        if (method, path) == ('GET', '123/media'):
            return {'data': self.rows}
        if (method, path) == ('POST', '123/media'):
            return {'id': 'container'}
        if (method, path) == ('GET', 'container'):
            if self.cutoff_during_processing:
                self.now = local('2026-10-04T14:00')
            return {'status_code': 'FINISHED'}
        if (method, path) == ('POST', '123/media_publish'):
            # Durable reservation must exist before any external publication.
            self.assertEqual(json.loads(self.ledger.read_text())['2026-10-04']['state'], 'submitting')
            if self.publish_error:
                raise TimeoutError('Simulated uncertain publish response')
            self.rows = [{'id': 'media', 'timestamp': '2026-10-04T17:17:00+00:00',
                          'permalink': 'https://example.invalid/post', 'caption': 'daily joke'}]
            return {'id': 'media'}
        if (method, path) == ('GET', 'media'):
            return {'id': 'media', 'permalink': 'https://example.invalid/post'}
        raise AssertionError('Unexpected API call: ' + repr((method, path)))

    def test_repeated_backups_publish_only_once(self):
        publisher.main()
        self.now = local('2026-10-04T12:37')
        publisher.main()
        self.now = local('2026-10-04T13:17')
        publisher.main()
        self.assertEqual(self.calls.count(('POST', '123/media_publish')), 1)
        self.assertEqual(self.render.call_count, 1)
        self.assertEqual(json.loads(self.ledger.read_text())['2026-10-04']['state'], 'published')

    def test_uncertain_submission_is_not_blindly_retried(self):
        self.publish_error = True
        with self.assertRaises(TimeoutError):
            publisher.main()
        self.assertEqual(json.loads(self.ledger.read_text())['2026-10-04']['state'], 'submitting')
        with self.assertRaisesRegex(RuntimeError, 'refusing a blind duplicate retry'):
            publisher.main()
        self.assertEqual(self.calls.count(('POST', '123/media_publish')), 1)

    def test_published_ledger_blocks_retry_when_feed_temporarily_empty(self):
        publisher.main()
        self.rows = []
        with self.assertRaisesRegex(RuntimeError, 'refusing a blind duplicate retry'):
            publisher.main()
        self.assertEqual(self.calls.count(('POST', '123/media_publish')), 1)

    def test_submitting_ledger_reconciles_an_existing_live_post(self):
        self.ledger.write_text(json.dumps({'2026-10-04': {'state': 'submitting', 'joke_index': 2}}))
        self.rows = [{'id': 'live', 'timestamp': '2026-10-04T17:05:00+00:00', 'caption': 'daily joke'}]
        publisher.main()
        self.assertFalse(any(method == 'POST' for method, _ in self.calls))
        entry = json.loads(self.ledger.read_text())['2026-10-04']
        self.assertEqual((entry['state'], entry['media_id'], entry['joke_index']), ('published', 'live', 2))

    def test_prepared_entry_reuses_content_on_backup(self):
        self.ledger.write_text(json.dumps({'2026-10-04': {
            'state': 'prepared', 'joke_index': 2, 'caption': 'prepared joke',
            'image_path': 'docs/circus-posts/2026-10-04.jpg', 'image_commit': 'existing',
        }}))
        publisher.main()
        self.render.assert_not_called()
        self.assertEqual(json.loads(self.ledger.read_text())['2026-10-04']['joke_index'], 2)

    def test_late_scheduled_run_does_not_touch_account_or_ledger(self):
        self.now = local('2026-10-04T15:33')
        publisher.main()
        self.assertEqual(self.calls, [])
        self.assertFalse(self.ledger.exists())

    def test_wrong_dst_slot_does_not_touch_account_or_ledger(self):
        self.event.write_text(json.dumps({'schedule': '0 18 * * *'}))
        publisher.main()
        self.assertEqual(self.calls, [])
        self.assertFalse(self.ledger.exists())

    def test_workflow_push_is_not_a_manual_override(self):
        os.environ['GITHUB_EVENT_NAME'] = 'push'
        publisher.main()
        self.assertEqual(self.calls, [])
        self.assertFalse(self.ledger.exists())

    def test_explicit_manual_dispatch_keeps_existing_override_and_duplicate_checks(self):
        os.environ['GITHUB_EVENT_NAME'] = 'workflow_dispatch'
        self.now = local('2026-10-04T19:00')
        publisher.main()
        publisher.main()
        self.assertEqual(self.calls.count(('POST', '123/media_publish')), 1)

    def test_cutoff_during_preparation_leaves_prepared_without_publish(self):
        self.cutoff_during_processing = True
        publisher.main()
        self.assertNotIn(('POST', '123/media_publish'), self.calls)
        self.assertEqual(json.loads(self.ledger.read_text())['2026-10-04']['state'], 'prepared')

    def test_cutoff_during_reservation_releases_only_unsubmitted_reservation(self):
        self.cutoff_during_reservation = True
        publisher.main()
        self.assertNotIn(('POST', '123/media_publish'), self.calls)
        entry = json.loads(self.ledger.read_text())['2026-10-04']
        self.assertEqual(entry['state'], 'prepared')
        self.assertNotIn('container_id', entry)


if __name__ == '__main__':
    unittest.main()
