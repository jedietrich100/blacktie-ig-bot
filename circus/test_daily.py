"""Offline safety coverage. All HTTP and Git operations are mocked."""
import contextlib
import datetime as dt
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import content
import daily


class DailySafetyTests(unittest.TestCase):
    DAY = '2026-10-01'
    USER = '123'
    CREATED = '456'
    MEDIA = '789'
    LINK = 'https://www.instagram.com/p/CircusTest_1/'

    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        original_cwd = Path.cwd()
        self.stack.callback(os.chdir, original_cwd)
        self.work = self.stack.enter_context(tempfile.TemporaryDirectory())
        os.chdir(self.work)
        self.env = {
            'CIRCUS_PUBLISH': 'true',
            'CIRCUS_IG_ACCESS_TOKEN': 'fake-test-token',
            'CIRCUS_IG_USER_ID': self.USER,
            'CIRCUS_REPOSITORY': 'jedietrich100/blacktie-ig-bot',
        }
        self.stack.enter_context(mock.patch.dict(os.environ, self.env, clear=True))
        self.stack.enter_context(mock.patch.multiple(daily,
            DAY=self.DAY,
            OUT=Path('docs/circus-posts') / self.DAY,
            STATE=Path('circus/state') / f'{self.DAY}.json',
            PREVIEW=Path('circus/preview')))
        image = io.BytesIO()
        daily.Image.new('RGB', (10, 10), 'white').save(image, 'JPEG')
        self.image = image.getvalue()
        self.caption = content.for_day(self.DAY)[2]
        self.render = self.stack.enter_context(mock.patch.object(
            daily, 'render', return_value=(self.image, self.caption)))
        self.stdout = self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.git = self.stack.enter_context(mock.patch.object(daily, 'git', return_value='a' * 40))
        self.stack.enter_context(mock.patch.object(daily.subprocess, 'run',
            side_effect=AssertionError('Real subprocess must never run')))
        self.stack.enter_context(mock.patch.object(daily.time, 'sleep'))
        self.account = {'id': self.USER, 'user_id': self.USER, 'username': daily.EXPECTED_USERNAME}
        self.rows = []
        self.overrides = {}
        self.events = []
        self.persist_fail = None
        self.persist = self.stack.enter_context(mock.patch.object(
            daily, 'persist', side_effect=self.fake_persist))
        self.http = self.stack.enter_context(mock.patch.object(
            daily.requests, 'request', side_effect=self.fake_request))
        public = mock.Mock(content=self.image)
        public.raise_for_status.return_value = None
        self.public = self.stack.enter_context(mock.patch.object(
            daily.requests, 'get', return_value=public))
        self.stack.enter_context(mock.patch.object(daily.requests, 'post',
            side_effect=AssertionError('Unexpected requests.post')))

    def fake_persist(self, message):
        self.events.append(('persist', self.read_state()['phase']))
        if self.persist_fail and self.persist_fail in message:
            raise RuntimeError('Mock persistence failure')

    def fake_request(self, method, url, **kwargs):
        prefix = daily.API + '/'
        self.assertTrue(url.startswith(prefix), url)
        path = url[len(prefix):]
        self.events.append((method, path))
        self.assertEqual(kwargs['headers'], {'Authorization': 'Bearer fake-test-token'})
        self.assertFalse(kwargs['allow_redirects'])
        self.assertNotIn('fake-test-token', url)
        for values in (kwargs.get('params'), kwargs.get('data')):
            self.assertNotIn('access_token', values or {})
        payload = self.overrides.get((method, path))
        if isinstance(payload, Exception):
            raise payload
        if payload is None:
            if (method, path) == ('GET', 'me'):
                payload = self.account
            elif (method, path) == ('GET', self.USER + '/media'):
                payload = {'data': self.rows}
            elif (method, path) == ('POST', self.USER + '/media'):
                payload = {'id': self.CREATED}
            elif (method, path) == ('GET', self.CREATED):
                payload = {'status_code': 'FINISHED'}
            elif (method, path) == ('POST', self.USER + '/media_publish'):
                payload = {'id': self.MEDIA}
            elif (method, path) == ('GET', self.MEDIA):
                payload = {'id': self.MEDIA, 'username': daily.EXPECTED_USERNAME, 'permalink': self.LINK}
            else:
                self.fail(f'Unexpected HTTP request: {method} {path}')
        return mock.Mock(status_code=200, json=mock.Mock(return_value=payload))

    def posts(self):
        return [call for call in self.http.call_args_list if call.args[0] == 'POST']

    def read_state(self):
        return json.loads(daily.STATE.read_text())

    def seed_state(self, phase='prepared', **extra):
        state = {'date': self.DAY, 'ig_user_id': self.USER, 'phase': phase, **extra}
        daily.write_state(state)
        daily.OUT.mkdir(parents=True, exist_ok=True)
        (daily.OUT / 'post.jpg').write_bytes(self.image)
        (daily.OUT / 'caption.txt').write_text('Saved prepared caption')
        return state

    def assert_no_post(self):
        self.assertEqual(self.posts(), [])

    def test_preview_no_http_git_or_state(self):
        os.environ['CIRCUS_PUBLISH'] = 'false'
        daily.main()
        self.http.assert_not_called()
        self.public.assert_not_called()
        self.git.assert_not_called()
        self.persist.assert_not_called()
        self.assertFalse(daily.STATE.exists())
        self.assertEqual((daily.PREVIEW / 'caption.txt').read_text(), self.caption)

    def test_repository_mismatch_no_http_or_post(self):
        os.environ['CIRCUS_REPOSITORY'] = 'somebody/other-repo'
        with self.assertRaisesRegex(RuntimeError, 'Unexpected repository'):
            daily.main()
        self.http.assert_not_called()
        self.persist.assert_not_called()

    def test_wrong_username_or_account_id_no_post(self):
        for field, value in [('username', 'otherbrand'), ('user_id', '999')]:
            with self.subTest(field=field):
                saved = self.account[field]
                self.account[field] = value
                with self.assertRaisesRegex(RuntimeError, 'Credentials do not match'):
                    daily.main()
                self.account[field] = saved
        self.assert_no_post()
        self.persist.assert_not_called()

    def test_invalid_configured_id_no_http(self):
        os.environ['CIRCUS_IG_USER_ID'] = '../other'
        with self.assertRaisesRegex(RuntimeError, 'Invalid configured'):
            daily.main()
        self.http.assert_not_called()

    def test_malformed_state_fails_closed(self):
        bad_states = [None, {}, [], 'bad',
            {'date': self.DAY, 'ig_user_id': self.USER, 'phase': 'unknown'},
            {'date': '2026-09-30', 'ig_user_id': self.USER, 'phase': 'prepared'},
            {'date': self.DAY, 'ig_user_id': '999', 'phase': 'prepared'}]
        for state in bad_states:
            with self.subTest(state=state):
                daily.write_state(state)
                with self.assertRaisesRegex(RuntimeError, 'Invalid existing'):
                    daily.main()
        daily.STATE.write_text('{broken')
        with self.assertRaises(json.JSONDecodeError):
            daily.main()
        self.assert_no_post()
        self.persist.assert_not_called()

    def test_unreadable_media_fails_closed(self):
        for payload in ({}, {'data': {}}, {'data': [{'timestamp': 'bad'}]},
                {'data': [{'timestamp': '2026-10-01T17:00:00'}]}, {'data': [{}]}):
            with self.subTest(payload=payload):
                self.overrides[('GET', self.USER + '/media')] = payload
                with self.assertRaises((RuntimeError, ValueError, KeyError)):
                    daily.main()
        self.assert_no_post()

    def test_same_day_duplicate_no_post_and_verifies_link(self):
        self.rows = [{'id': self.MEDIA, 'timestamp': '2026-10-02T01:00:00Z', 'caption': 'Anything'}]
        daily.main()
        self.assert_no_post()
        self.persist.assert_not_called()
        self.assertIn(self.LINK, self.stdout.getvalue())
        self.assertFalse(daily.STATE.exists())

    def test_yesterday_identical_caption_does_not_block(self):
        self.rows = [{'id': '987', 'timestamp': '2026-10-01T04:59:59Z', 'caption': self.caption}]
        daily.main()
        self.assertEqual(len(self.posts()), 2)
        self.assertEqual(self.read_state()['phase'], 'published')

    def test_prepared_resume_preserves_saved_caption(self):
        self.seed_state()
        daily.main()
        self.assertEqual(self.posts()[0].kwargs['data']['caption'], 'Saved prepared caption')
        self.assertFalse(any('prepared:' in call.args[0] for call in self.persist.call_args_list))

    def test_preparation_or_submitting_persist_failure_prevents_container(self):
        for failure, phase in [('prepared:', 'prepared'), ('submitting:', 'submitting')]:
            with self.subTest(failure=failure):
                if daily.STATE.exists():
                    daily.STATE.unlink()
                self.persist_fail = failure
                with self.assertRaisesRegex(RuntimeError, 'Mock persistence'):
                    daily.main()
                self.assertEqual(self.read_state()['phase'], phase)
        self.assert_no_post()

    def test_container_persist_failure_prevents_publish_and_rerun(self):
        self.persist_fail = 'container created:'
        with self.assertRaisesRegex(RuntimeError, 'Mock persistence'):
            daily.main()
        self.assertEqual(self.read_state()['creation_id'], self.CREATED)
        self.assertEqual(self.read_state()['phase'], 'container_created')
        self.persist_fail = None
        with self.assertRaisesRegex(RuntimeError, 'Uncertain prior'):
            daily.main()
        self.assertEqual(len(self.posts()), 1)

    def test_publishing_persist_failure_prevents_publish(self):
        self.persist_fail = 'publishing:'
        with self.assertRaisesRegex(RuntimeError, 'Mock persistence'):
            daily.main()
        self.assertEqual(self.read_state()['phase'], 'publishing')
        self.assertEqual(len(self.posts()), 1)

    def test_uncertain_existing_state_never_blindly_retries(self):
        for phase in ('submitting', 'container_created', 'publishing'):
            with self.subTest(phase=phase):
                self.seed_state(phase, creation_id=self.CREATED)
                with self.assertRaisesRegex(RuntimeError, 'Uncertain prior'):
                    daily.main()
        self.assert_no_post()
        self.public.assert_not_called()

    def test_container_creation_timeout_stays_uncertain(self):
        self.overrides[('POST', self.USER + '/media')] = daily.requests.Timeout('fake')
        with self.assertRaises(daily.requests.Timeout):
            daily.main()
        self.assertEqual(self.read_state()['phase'], 'submitting')
        with self.assertRaisesRegex(RuntimeError, 'Uncertain prior'):
            daily.main()
        self.assertEqual(len(self.posts()), 1)

    def test_container_poll_timeout_keeps_id_and_never_publishes(self):
        self.overrides[('GET', self.CREATED)] = daily.requests.Timeout('fake')
        with self.assertRaises(daily.requests.Timeout):
            daily.main()
        self.assertEqual(self.read_state()['phase'], 'container_created')
        self.assertEqual(self.read_state()['creation_id'], self.CREATED)
        with self.assertRaisesRegex(RuntimeError, 'Uncertain prior'):
            daily.main()
        self.assertEqual(len(self.posts()), 1)

    def test_container_error_or_never_finished_does_not_publish(self):
        for status in ('ERROR', 'EXPIRED', 'IN_PROGRESS'):
            with self.subTest(status=status):
                self.seed_state()
                self.http.reset_mock()
                self.overrides[('GET', self.CREATED)] = {'status_code': status}
                with self.assertRaises(RuntimeError):
                    daily.main()
                self.assertEqual(len(self.posts()), 1)
                self.assertEqual(self.read_state()['phase'], 'container_created')

    def test_publish_timeout_never_reposts(self):
        self.overrides[('POST', self.USER + '/media_publish')] = daily.requests.Timeout('fake')
        with self.assertRaises(daily.requests.Timeout):
            daily.main()
        self.assertEqual(self.read_state()['phase'], 'publishing')
        with self.assertRaisesRegex(RuntimeError, 'Uncertain prior'):
            daily.main()
        self.assertEqual(len(self.posts()), 2)

    def test_ambiguous_publish_reconciles_existing_post_without_retry(self):
        self.seed_state('publishing', creation_id=self.CREATED)
        self.rows = [{'id': self.MEDIA, 'timestamp': '2026-10-01T17:05:00+00:00'}]
        daily.main()
        self.assert_no_post()
        self.assertIn(self.LINK, self.stdout.getvalue())

    def test_success_persists_order_and_verified_permalink(self):
        daily.main()
        self.assertEqual(self.events, [
            ('GET', 'me'), ('GET', self.USER + '/media'),
            ('persist', 'prepared'), ('persist', 'submitting'),
            ('POST', self.USER + '/media'), ('persist', 'container_created'),
            ('GET', self.CREATED), ('persist', 'publishing'),
            ('POST', self.USER + '/media_publish'), ('persist', 'published'),
            ('GET', self.MEDIA), ('persist', 'published')])
        state = self.read_state()
        self.assertEqual(state['instagram_media_id'], self.MEDIA)
        self.assertEqual(state['creation_id'], self.CREATED)
        self.assertEqual(state['permalink'], self.LINK)
        self.assertIn('VERIFIED_PERMALINK: ' + self.LINK, self.stdout.getvalue())
        self.assertEqual(len(self.posts()), 2)

    def test_published_state_verifies_without_reposting(self):
        self.seed_state('published', instagram_media_id=self.MEDIA)
        daily.main()
        self.assert_no_post()
        self.public.assert_not_called()
        self.assertIn(self.LINK, self.stdout.getvalue())

    def test_published_persistence_failure_rerun_does_not_duplicate(self):
        self.persist_fail = 'published:'
        with self.assertRaisesRegex(RuntimeError, 'Mock persistence'):
            daily.main()
        self.assertEqual(self.read_state()['phase'], 'published')
        self.persist_fail = None
        daily.main()
        self.assertEqual(len(self.posts()), 2)

    def test_permalink_mismatch_fails_after_success_without_reposting(self):
        self.overrides[('GET', self.MEDIA)] = {
            'id': self.MEDIA, 'username': 'otherbrand', 'permalink': self.LINK}
        with self.assertRaisesRegex(RuntimeError, 'identity'):
            daily.main()
        self.assertEqual(self.read_state()['phase'], 'published')
        with self.assertRaisesRegex(RuntimeError, 'identity'):
            daily.main()
        self.assertEqual(len(self.posts()), 2)

    def test_untrusted_permalink_is_rejected(self):
        for url in ('https://evil.example/p/123', 'https://www.instagram.com.evil.example/p/123',
                    'javascript:alert(1)', 'https://www.instagram.com/circuspeanutsdaily/'):
            with self.subTest(url=url):
                self.overrides[('GET', self.MEDIA)] = {
                    'id': self.MEDIA, 'username': daily.EXPECTED_USERNAME, 'permalink': url}
                with self.assertRaisesRegex(RuntimeError, 'permalink'):
                    daily.verified_permalink(self.MEDIA, 'fake-test-token')


class ContentTests(unittest.TestCase):
    def test_sixty_consecutive_days_are_unique_then_repeat(self):
        start = content.START
        jokes = [content.for_day((start + dt.timedelta(days=i)).isoformat())[:2] for i in range(60)]
        self.assertEqual(len(content.JOKES), 60)
        self.assertEqual(len(set(jokes)), 60)
        self.assertEqual(jokes[0], content.for_day((start + dt.timedelta(days=60)).isoformat())[:2])

    def test_all_sixty_cards_render_as_expected_jpeg(self):
        for i in range(60):
            day = (content.START + dt.timedelta(days=i)).isoformat()
            with self.subTest(day=day), mock.patch.object(daily, 'DAY', day):
                data, caption = daily.render()
                with daily.Image.open(io.BytesIO(data)) as image:
                    self.assertEqual(image.format, 'JPEG')
                    self.assertEqual(image.size, (1080, 1350))
                    self.assertEqual(image.mode, 'RGB')
                self.assertEqual(caption, content.for_day(day)[2])


if __name__ == '__main__':
    unittest.main()
