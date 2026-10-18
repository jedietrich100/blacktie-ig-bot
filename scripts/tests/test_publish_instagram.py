"""Offline safety tests: no real API, git, token, or publication is used."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "publish_instagram.py"
SPEC = importlib.util.spec_from_file_location("publish_instagram", MODULE_PATH)
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)

DAY = "2026-10-18"
CAPTION = "Black Tie Intel | 2026-10-18\nPreserved exact daily caption."
IMAGE = "https://raw.githubusercontent.com/example/repo/immutable-sha/daily.jpg"
CONTAINER = "18107224811148189"
MEDIA = "18000000000000001"


def row(day=DAY, caption=CAPTION, media_id=MEDIA):
    return {
        "id": media_id,
        "caption": caption,
        "timestamp": day + "T14:00:00+00:00",
        "permalink": "https://www.instagram.com/p/VerifiedPost/",
    }


class FakeAPI:
    def __init__(self):
        self.calls = []
        self.identity = {"user_id": publisher.EXPECTED_ID, "username": publisher.EXPECTED_USERNAME}
        self.feed = []
        self.feed_pages = None
        self.feed_error = None
        self.container_status = "FINISHED"
        self.publish_outcomes = []
        self.on_publish = None
        self.readback = row()

    def __call__(self, method, path, token, params=None, data=None):
        self.calls.append((method, path, copy.deepcopy(params), copy.deepcopy(data)))
        if method == "GET" and path == "me":
            return self.identity
        if method == "GET" and path == publisher.EXPECTED_ID + "/media":
            if self.feed_error:
                raise self.feed_error
            if self.feed_pages is not None:
                return self.feed_pages[params.get("after")]
            return {"data": self.feed}
        if method == "GET" and path == CONTAINER:
            return {"status_code": self.container_status}
        if method == "GET" and path == MEDIA:
            if isinstance(self.readback, BaseException):
                raise self.readback
            return self.readback
        if method == "POST" and path == publisher.EXPECTED_ID + "/media":
            return {"id": CONTAINER}
        if method == "POST" and path == publisher.EXPECTED_ID + "/media_publish":
            if self.on_publish:
                self.on_publish()
            outcome = self.publish_outcomes.pop(0) if self.publish_outcomes else {"id": MEDIA}
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        raise AssertionError("Unexpected fake request: " + method + " " + path)

    def posts(self, suffix=None):
        return [call for call in self.calls if call[0] == "POST" and
                (suffix is None or call[1].endswith(suffix))]


class PublisherSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "ledger.json"
        self.api = FakeAPI()
        self.snapshots = []
        self.remote = None
        self.sleeps = []
        self.api_patch = mock.patch.object(publisher, "api_request", self.api)
        self.api_patch.start()
        self.addCleanup(self.api_patch.stop)
        self.print_patch = mock.patch("builtins.print")
        self.print_patch.start()
        self.addCleanup(self.print_patch.stop)

    def checkpoint(self, path):
        self.remote = json.loads(path.read_text())
        self.snapshots.append(copy.deepcopy(self.remote[DAY]))

    def seed(self, status="prepared", **values):
        entry = {
            "account_id": publisher.EXPECTED_ID,
            "image_url": IMAGE,
            "caption_sha256": hashlib.sha256(CAPTION.encode()).hexdigest(),
            "container_id": CONTAINER,
            "status": status,
        }
        entry.update(values)
        publisher.write_ledger(self.path, {DAY: entry})

    def run_publish(self, **kwargs):
        options = dict(image_url=IMAGE, caption=CAPTION, day=DAY, token="fake-token",
                       ledger_path=self.path, checkpoint=self.checkpoint, sleep=self.sleeps.append)
        options.update(kwargs)
        return publisher.publish_once(**options)

    def entry(self):
        return json.loads(self.path.read_text())[DAY]

    def test_success_has_durable_publishing_barrier_before_post(self):
        self.api.on_publish = lambda: self.assertEqual(self.remote[DAY]["status"], "publishing")
        result = self.run_publish()
        self.assertEqual(result["id"], MEDIA)
        self.assertEqual(len(self.api.posts("/media")), 1)
        self.assertEqual(len(self.api.posts("/media_publish")), 1)
        self.assertEqual(self.remote[DAY]["status"], "published")

    def test_known_not_ready_retries_only_same_existing_container(self):
        self.seed()
        self.api.publish_outcomes = [publisher.ApiError(400, 9007, 2207027), {"id": MEDIA}]
        self.run_publish(existing_container=CONTAINER)
        self.assertEqual(self.api.posts("/media"), [])
        self.assertEqual([c[3]["creation_id"] for c in self.api.posts("/media_publish")], [CONTAINER] * 2)
        self.assertEqual(self.sleeps, [5])

    def test_known_not_ready_retry_budget_is_bounded(self):
        self.seed()
        count = len(publisher.PUBLISH_DELAYS) + 1
        self.api.publish_outcomes = [publisher.ApiError(400, 9007, 2207027) for _ in range(count)]
        with self.assertRaisesRegex(publisher.PublishError, "budget exhausted"):
            self.run_publish()
        self.assertEqual(len(self.api.posts("/media_publish")), count)
        self.assertEqual(self.entry()["status"], "ready_retry")

    def test_wrong_account_identity_stops_before_any_post(self):
        for identity in [
            {"user_id": "111", "username": publisher.EXPECTED_USERNAME},
            {"user_id": publisher.EXPECTED_ID, "username": "wrong_account"},
        ]:
            with self.subTest(identity=identity):
                self.api.identity = identity
                with self.assertRaisesRegex(publisher.PublishError, "expected Black Tie"):
                    self.run_publish()
                self.assertEqual(self.api.posts(), [])
                self.assertFalse(self.path.exists())

    def test_feed_read_failure_prevents_creation(self):
        self.api.feed_error = publisher.PublishError("feed unavailable")
        with self.assertRaisesRegex(publisher.PublishError, "feed unavailable"):
            self.run_publish()
        self.assertEqual(self.api.posts(), [])

    def test_complete_feed_pagination_finds_existing_post(self):
        self.api.feed_pages = {
            None: {"data": [row("2026-10-19", "newer unrelated post")],
                   "paging": {"next": "opaque", "cursors": {"after": "page2"}}},
            "page2": {"data": [row(), row("2026-10-17", "older post")]},
        }
        result = self.run_publish()
        self.assertEqual(result["id"], MEDIA)
        self.assertEqual(self.api.posts(), [])
        self.assertEqual(self.entry()["status"], "published")

    def test_incomplete_or_cyclic_pagination_stops_before_post(self):
        variants = [
            {None: {"data": [], "paging": {"next": "opaque"}}},
            {None: {"data": [row("2026-10-19", "newer")], "paging": {"next": "opaque"}}},
            {None: {"data": [row("2026-10-19", "newer")],
                    "paging": {"next": "opaque", "cursors": {"after": "repeat"}}},
             "repeat": {"data": [row("2026-10-19", "newer")],
                        "paging": {"next": "opaque", "cursors": {"after": "repeat"}}}},
        ]
        for pages in variants:
            with self.subTest(pages=pages):
                self.api.feed_pages = pages
                with self.assertRaisesRegex(publisher.PublishError, "pagination is incomplete"):
                    self.run_publish()
                self.assertEqual(self.api.posts(), [])

    def test_unordered_feed_stops_before_post(self):
        self.api.feed = [row("2026-10-17", "older"), row()]
        with self.assertRaisesRegex(publisher.PublishError, "ordering is ambiguous"):
            self.run_publish()
        self.assertEqual(self.api.posts(), [])

    def test_exact_caption_after_midnight_reconciles_without_publication(self):
        self.api.feed = [row("2026-10-19")]
        self.run_publish()
        self.assertEqual(self.api.posts(), [])
        self.assertEqual(self.entry()["published_at"], "2026-10-19T14:00:00+00:00")

    def test_other_same_day_media_blocks_publication(self):
        self.api.feed = [row(caption="A different daily post")]
        with self.assertRaisesRegex(publisher.PublishError, "other media for this date"):
            self.run_publish()
        self.assertEqual(self.api.posts(), [])

    def test_altered_reserved_caption_or_image_stops_before_post(self):
        self.seed()
        for changes in [{"caption": CAPTION + " changed"}, {"image_url": IMAGE + "changed"}]:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(publisher.PublishError, "differs from its durable reservation"):
                    self.run_publish(**changes)
                self.assertEqual(self.api.posts(), [])

    def test_recovery_container_must_match_reservation(self):
        self.seed()
        with self.assertRaisesRegex(publisher.PublishError, "Recovery container differs"):
            self.run_publish(existing_container="999999")
        self.assertEqual(self.api.posts(), [])

    def test_recovery_container_requires_trusted_reservation(self):
        with self.assertRaisesRegex(publisher.PublishError, "trusted durable reservation"):
            self.run_publish(existing_container=CONTAINER)
        self.assertEqual(self.api.posts(), [])
        self.assertFalse(self.path.exists())

    def test_prior_uncertain_or_terminal_states_never_republish_absent_feed(self):
        for status in ["publishing", "unknown", "published_unverified", "published", "blocked", "creating"]:
            with self.subTest(status=status):
                self.seed(status)
                with self.assertRaisesRegex(publisher.PublishError, "no automatic resubmission"):
                    self.run_publish()
                self.assertEqual(self.api.posts(), [])

    def test_unrecognized_ledger_status_fails_closed(self):
        self.seed("unexpected_status")
        with self.assertRaises(publisher.PublishError):
            self.run_publish()
        self.assertEqual(self.api.posts(), [])

    def test_prior_unknown_can_reconcile_matching_feed_without_post(self):
        self.seed("unknown")
        self.api.feed = [row()]
        self.run_publish()
        self.assertEqual(self.api.posts(), [])
        self.assertEqual(self.entry()["status"], "published")

    def test_published_container_with_delayed_feed_is_never_resubmitted(self):
        self.seed()
        self.api.container_status = "PUBLISHED"
        with self.assertRaisesRegex(publisher.PublishError, "receipt is not yet visible"):
            self.run_publish()
        self.assertEqual(self.api.posts(), [])
        self.assertEqual(self.entry()["status"], "unknown")

    def test_expired_and_error_container_are_not_recreated(self):
        for status in ["EXPIRED", "ERROR"]:
            with self.subTest(status=status):
                self.seed()
                self.api.container_status = status
                with self.assertRaisesRegex(publisher.PublishError, "cannot be published"):
                    self.run_publish()
                self.assertEqual(self.api.posts(), [])
                self.assertEqual(self.entry()["status"], "blocked")

    def test_initial_checkpoint_failure_prevents_all_posts(self):
        def fail_checkpoint(path):
            raise publisher.PublishError("checkpoint failed")
        with self.assertRaisesRegex(publisher.PublishError, "checkpoint failed"):
            self.run_publish(checkpoint=fail_checkpoint)
        self.assertEqual(self.api.posts(), [])

    def test_publishing_checkpoint_failure_prevents_publish_post(self):
        self.seed()
        def fail_before_publish(path):
            if json.loads(path.read_text())[DAY]["status"] == "publishing":
                raise publisher.PublishError("checkpoint failed")
            self.checkpoint(path)
        with self.assertRaisesRegex(publisher.PublishError, "checkpoint failed"):
            self.run_publish(checkpoint=fail_before_publish)
        self.assertEqual(self.api.posts(), [])

    def test_ambiguous_publish_timeout_never_retries(self):
        self.seed()
        self.api.publish_outcomes = [publisher.PublishError("request outcome is unknown")]
        with self.assertRaisesRegex(publisher.PublishError, "outcome is unknown"):
            self.run_publish()
        self.assertEqual(len(self.api.posts("/media_publish")), 1)
        self.assertEqual(self.remote[DAY]["status"], "unknown")

    def test_crash_after_publish_remains_blocked_after_durable_restore(self):
        self.seed()
        self.api.publish_outcomes = [SystemExit("simulated worker crash")]
        with self.assertRaises(SystemExit):
            self.run_publish()
        self.assertEqual(self.remote[DAY]["status"], "publishing")
        # Restore only what reached durable storage, as a fresh Actions runner would.
        publisher.write_ledger(self.path, self.remote)
        self.api.calls.clear()
        with self.assertRaisesRegex(publisher.PublishError, "no automatic resubmission"):
            self.run_publish()
        self.assertEqual(self.api.posts(), [])

    def test_missing_publish_id_never_retries(self):
        self.seed()
        self.api.publish_outcomes = [{}]
        with self.assertRaisesRegex(publisher.PublishError, "no valid media ID"):
            self.run_publish()
        self.assertEqual(len(self.api.posts("/media_publish")), 1)
        self.assertEqual(self.entry()["status"], "unknown")

    def test_readback_failure_preserves_success_receipt_and_blocks_retry(self):
        self.seed()
        self.api.readback = publisher.PublishError("readback unavailable")
        with self.assertRaisesRegex(publisher.PublishError, "readback unavailable"):
            self.run_publish()
        self.assertEqual(self.remote[DAY]["status"], "published_unverified")
        self.assertEqual(self.remote[DAY]["media_id"], MEDIA)
        self.api.calls.clear()
        with self.assertRaisesRegex(publisher.PublishError, "no automatic resubmission"):
            self.run_publish()
        self.assertEqual(self.api.posts(), [])

    def test_other_api_error_never_retries(self):
        self.seed()
        self.api.publish_outcomes = [publisher.ApiError(500, 2, None)]
        with self.assertRaisesRegex(publisher.PublishError, "not retried"):
            self.run_publish()
        self.assertEqual(len(self.api.posts("/media_publish")), 1)
        self.assertEqual(self.entry()["status"], "unknown")

    def test_not_ready_retry_requires_exact_status_code_and_subcode(self):
        for error in [publisher.ApiError(400, 9007, None),
                      publisher.ApiError(400, 9007, 2207008),
                      publisher.ApiError(500, 9007, 2207027)]:
            with self.subTest(error=str(error)):
                self.seed()
                self.api.calls.clear()
                self.api.publish_outcomes = [error]
                with self.assertRaisesRegex(publisher.PublishError, "not retried"):
                    self.run_publish()
                self.assertEqual(len(self.api.posts("/media_publish")), 1)
                self.assertEqual(self.entry()["status"], "unknown")

    def test_multiple_matching_media_fail_closed(self):
        self.api.feed = [row(media_id="111"), row(media_id="222")]
        with self.assertRaisesRegex(publisher.PublishError, "Multiple matching posts"):
            self.run_publish()
        self.assertEqual(self.api.posts(), [])


if __name__ == "__main__":
    unittest.main()
