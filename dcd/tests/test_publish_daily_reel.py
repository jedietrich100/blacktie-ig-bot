"""Offline tests: all Buffer/network calls and production Git operations mocked."""

import contextlib
import copy
import datetime as dt
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import publish_daily_reel as reel


def local(value):
    return dt.datetime.fromisoformat(value).replace(tzinfo=reel.ZONE)


class WindowTests(unittest.TestCase):
    def test_schedule_boundaries_in_both_dst_seasons(self):
        for date in ("2026-10-04", "2026-12-04"):
            for time, expected in (("17:29:59", False), ("17:30:00", True),
                                   ("17:40:00", True), ("17:50:00", True),
                                   ("17:59:59", True), ("18:00:00", False),
                                   ("21:56:00", False), ("22:00:00", False)):
                with self.subTest(date=date, time=time):
                    self.assertEqual(reel.publication_allowed("schedule", local(date + "T" + time), date), expected)

    def test_utc_conversion(self):
        self.assertTrue(reel.publication_allowed("schedule", dt.datetime.fromisoformat("2026-10-04T22:40:00+00:00"), "2026-10-04"))
        self.assertTrue(reel.publication_allowed("schedule", dt.datetime.fromisoformat("2026-12-04T23:40:00+00:00"), "2026-12-04"))

    def test_never_publish_prior_day(self):
        for event in ("schedule", "workflow_dispatch"):
            self.assertFalse(reel.publication_allowed(event, local("2026-10-05T17:40:00"), "2026-10-04"))

    def test_existing_explicit_manual_path_preserved(self):
        self.assertTrue(reel.publication_allowed("workflow_dispatch", local("2026-10-04T09:00:00"), "2026-10-04"))

    def test_unsupported_events_cannot_publish(self):
        for event in ("", "push", "pull_request", "workflow_run"):
            self.assertFalse(reel.publication_allowed(event, local("2026-10-04T17:40:00"), "2026-10-04"))


class MainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "dcd").mkdir()
        (self.root / "docs/dcd-reels").mkdir(parents=True)
        self.today = "2026-10-04"
        self.history = ["2026-10-02"]
        self.ledger = {}
        self.write_state()
        (self.root / "docs/dcd-reels/2026-10-04.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
        (self.root / "docs/dcd-reels/2026-10-04.txt").write_text("Today's how-to\n", encoding="utf-8")
        self.clock = local("2026-10-04T17:40:00")
        self.patchers = [
            patch.object(reel, "ROOT", self.root),
            patch.object(reel, "now", side_effect=lambda: self.clock),
            patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule", "DCD_BUFFER_API_KEY": "test-only",
                                  "GITHUB_REPOSITORY": "test/repository", "GITHUB_RUN_ID": "123",
                                  "GITHUB_STEP_SUMMARY": str(self.root / "summary")}, clear=True),
            patch.object(reel, "refresh_main"),
            patch.object(reel, "git", return_value="a" * 40),
            patch.object(reel, "verify_video"),
            patch.object(reel, "discover_channel", return_value="dcd-channel"),
            patch.object(reel, "publish_reel", return_value="buffer-post-123"),
            patch.object(reel, "persist", side_effect=self.save_state),
            patch("requests.sessions.Session.request", side_effect=AssertionError("Network forbidden in tests")),
        ]
        for item in self.patchers:
            item.start()
            self.addCleanup(item.stop)
        self.saved_states = []

    def write_state(self):
        (self.root / reel.HISTORY_PATH).write_text(json.dumps(self.history), encoding="utf-8")
        (self.root / reel.LEDGER_PATH).write_text(json.dumps(self.ledger), encoding="utf-8")

    def save_state(self, history, ledger, message):
        self.history = copy.deepcopy(history)
        self.ledger = copy.deepcopy(ledger)
        self.saved_states.append((copy.deepcopy(history), copy.deepcopy(ledger), message))
        self.write_state()

    def run_main(self):
        with contextlib.redirect_stdout(io.StringIO()):
            reel.main()

    def test_reservation_is_persisted_before_exactly_one_mutation(self):
        def inspect(*args):
            self.assertEqual(self.ledger[self.today]["state"], "submitting")
            self.assertNotIn(self.today, self.history)
            return "buffer-post-123"
        reel.publish_reel.side_effect = inspect
        self.run_main()
        reel.refresh_main.assert_called_once()
        reel.publish_reel.assert_called_once()
        self.assertEqual(self.ledger[self.today]["state"], "submitted")
        self.assertEqual(self.ledger[self.today]["buffer_post_id"], "buffer-post-123")
        self.assertIn(self.today, self.history)
        self.assertEqual(len(self.saved_states), 2)

    def test_second_attempt_reads_saved_receipt_and_skips(self):
        self.run_main()
        self.run_main()
        reel.publish_reel.assert_called_once()

    def test_existing_legacy_history_skips(self):
        self.history.append(self.today)
        self.write_state()
        self.run_main()
        reel.publish_reel.assert_not_called()
        reel.verify_video.assert_not_called()

    def test_fresh_main_is_loaded_before_history_check(self):
        def refresh():
            self.history.append(self.today)
            self.write_state()
        reel.refresh_main.side_effect = refresh
        self.run_main()
        reel.publish_reel.assert_not_called()

    def test_timeout_retains_reservation_and_next_attempt_cannot_resubmit(self):
        reel.publish_reel.side_effect = reel.requests.Timeout("response lost")
        with self.assertRaisesRegex(RuntimeError, "outcome is uncertain"):
            self.run_main()
        self.assertEqual(self.ledger[self.today]["state"], "submitting")
        with self.assertRaisesRegex(RuntimeError, "reconciliation"):
            self.run_main()
        reel.publish_reel.assert_called_once()

    def test_buffer_error_is_conservatively_not_retried(self):
        reel.publish_reel.side_effect = RuntimeError("Buffer rejected or malformed reply")
        with self.assertRaisesRegex(RuntimeError, "outcome is uncertain"):
            self.run_main()
        self.assertEqual(self.ledger[self.today]["state"], "submitting")
        reel.publish_reel.assert_called_once()

    def test_missing_post_id_retains_reservation(self):
        reel.publish_reel.return_value = ""
        with self.assertRaisesRegex(RuntimeError, "outcome is uncertain"):
            self.run_main()
        self.assertEqual(self.ledger[self.today]["state"], "submitting")

    def test_cancellation_after_reservation_blocks_next_attempt(self):
        reel.publish_reel.side_effect = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.run_main()
        with self.assertRaisesRegex(RuntimeError, "reconciliation"):
            self.run_main()
        reel.publish_reel.assert_called_once()

    def test_missing_key_prevents_git_and_mutation(self):
        with patch.dict(os.environ, {"DCD_BUFFER_API_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "not configured"):
                self.run_main()
        reel.refresh_main.assert_not_called()
        reel.publish_reel.assert_not_called()

    def test_reservation_push_failure_prevents_mutation(self):
        reel.persist.side_effect = subprocess.CalledProcessError(1, "git push")
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_main()
        reel.publish_reel.assert_not_called()

    def test_receipt_push_failure_blocks_next_attempt(self):
        def save_reservation_only(history, ledger, message):
            if ledger[self.today]["state"] == "submitted":
                raise subprocess.CalledProcessError(1, "git push")
            self.save_state(history, ledger, message)
        reel.persist.side_effect = save_reservation_only
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_main()
        with self.assertRaisesRegex(RuntimeError, "reconciliation"):
            self.run_main()
        reel.publish_reel.assert_called_once()

    def test_accepted_receipt_reconciles_missing_history_without_mutation(self):
        self.ledger[self.today] = {"state": "submitted", "buffer_post_id": "existing-post"}
        self.write_state()
        self.run_main()
        self.assertIn(self.today, self.history)
        reel.publish_reel.assert_not_called()

    def test_unrecognized_ledger_state_blocks(self):
        self.ledger[self.today] = {"state": "unexpected"}
        self.write_state()
        with self.assertRaisesRegex(RuntimeError, "reconciliation"):
            self.run_main()
        reel.publish_reel.assert_not_called()

    def test_missing_legacy_history_blocks(self):
        (self.root / reel.HISTORY_PATH).unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_main()
        reel.publish_reel.assert_not_called()

    def test_invalid_state_blocks(self):
        for path, payload in ((reel.HISTORY_PATH, {}), (reel.LEDGER_PATH, []), (reel.LEDGER_PATH, {self.today: "wrong"})):
            with self.subTest(path=path, payload=payload):
                self.write_state()
                (self.root / path).write_text(json.dumps(payload))
                with self.assertRaises(RuntimeError):
                    self.run_main()
        reel.publish_reel.assert_not_called()

    def test_malformed_json_blocks(self):
        (self.root / reel.LEDGER_PATH).write_text("{broken")
        with self.assertRaises(json.JSONDecodeError):
            self.run_main()
        reel.publish_reel.assert_not_called()

    def test_missing_ledger_blocks_instead_of_resetting_duplicate_protection(self):
        (self.root / reel.LEDGER_PATH).unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_main()
        reel.publish_reel.assert_not_called()

    def test_missing_optional_reel_skips(self):
        (self.root / "docs/dcd-reels/2026-10-04.mp4").unlink()
        self.run_main()
        reel.publish_reel.assert_not_called()
        reel.persist.assert_not_called()

    def test_empty_caption_blocks(self):
        (self.root / "docs/dcd-reels/2026-10-04.txt").write_text(" \n")
        with self.assertRaisesRegex(RuntimeError, "caption is empty"):
            self.run_main()
        reel.publish_reel.assert_not_called()

    def test_media_failure_leaves_safe_retry_available(self):
        reel.verify_video.side_effect = RuntimeError("MP4 unavailable")
        with self.assertRaises(RuntimeError):
            self.run_main()
        reel.persist.assert_not_called()
        reel.publish_reel.assert_not_called()
        reel.verify_video.side_effect = None
        self.run_main()
        reel.publish_reel.assert_called_once()

    def test_channel_discovery_failure_has_no_reservation(self):
        reel.discover_channel.side_effect = RuntimeError("channel unavailable")
        with self.assertRaises(RuntimeError):
            self.run_main()
        reel.persist.assert_not_called()
        reel.publish_reel.assert_not_called()

    def test_outside_window_does_no_git_or_network_work(self):
        self.clock = local("2026-10-04T21:56:00")
        self.run_main()
        reel.refresh_main.assert_not_called()
        reel.discover_channel.assert_not_called()
        reel.publish_reel.assert_not_called()

    def test_cutoff_during_preparation_prevents_reservation(self):
        def close_window(*args):
            self.clock = local("2026-10-04T18:00:00")
        reel.verify_video.side_effect = close_window
        self.run_main()
        reel.persist.assert_not_called()
        reel.publish_reel.assert_not_called()

    def test_cutoff_during_persist_releases_only_unsent_reservation(self):
        def persist_and_close(history, ledger, message):
            self.save_state(history, ledger, message)
            self.clock = local("2026-10-04T18:00:00")
        reel.persist.side_effect = persist_and_close
        self.run_main()
        self.assertEqual(self.ledger[self.today]["state"], "deferred")
        self.assertNotIn(self.today, self.history)
        reel.publish_reel.assert_not_called()

    def test_midnight_during_preparation_cannot_backfill(self):
        def next_day(*args):
            self.clock = local("2026-10-05T00:00:01")
        reel.verify_video.side_effect = next_day
        self.run_main()
        reel.publish_reel.assert_not_called()

    def test_safely_deferred_state_may_retry_in_window(self):
        self.ledger[self.today] = {"state": "deferred"}
        self.write_state()
        self.run_main()
        reel.publish_reel.assert_called_once()


class GitAndVideoTests(unittest.TestCase):
    def test_refresh_main_rejects_other_branch(self):
        with patch.object(reel, "git", return_value="feature") as git:
            with self.assertRaises(RuntimeError):
                reel.refresh_main()
            git.assert_called_once()

    def test_refresh_main_pulls_before_state_read(self):
        with patch.object(reel, "git", side_effect=["main", ""]) as git:
            reel.refresh_main()
            self.assertEqual(git.call_args_list[-1].args, ("pull", "--ff-only", "origin", "main"))

    def test_verify_mp4_signature(self):
        with patch.object(reel.requests, "get", return_value=Mock(ok=True, content=b"\x00\x00\x00\x18ftypmp42")) as get:
            reel.verify_video("https://test.invalid/video.mp4")
            get.assert_called_once()

    def test_verify_rejects_html_and_retries_only_reads(self):
        with patch.object(reel.requests, "get", return_value=Mock(ok=True, content=b"<html>bad</html>")) as get, patch.object(reel.time, "sleep"):
            with self.assertRaises(RuntimeError):
                reel.verify_video("https://test.invalid/video.mp4")
            self.assertEqual(get.call_count, 6)

    def test_verify_read_timeout_is_bounded(self):
        with patch.object(reel.requests, "get", side_effect=reel.requests.Timeout) as get, patch.object(reel.time, "sleep"):
            with self.assertRaises(RuntimeError):
                reel.verify_video("https://test.invalid/video.mp4")
            self.assertEqual(get.call_count, 6)


class LocalGitPersistenceTests(unittest.TestCase):
    """Exercise real commit/rebase/push using only a temporary local bare repo."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.remote = self.base / "origin.git"
        self.work = self.base / "work"
        self.other = self.base / "other"
        self.command(self.base, "init", "--bare", "--initial-branch=main", str(self.remote))
        self.command(self.base, "clone", str(self.remote), str(self.work))
        self.command(self.work, "config", "user.name", "Offline Test")
        self.command(self.work, "config", "user.email", "offline@example.invalid")
        (self.work / "dcd").mkdir()
        (self.work / reel.HISTORY_PATH).write_text("[]\n")
        (self.work / reel.LEDGER_PATH).write_text("{}\n")
        self.command(self.work, "add", ".")
        self.command(self.work, "commit", "-m", "Initial test state")
        self.command(self.work, "push", "origin", "main")
        self.command(self.base, "clone", str(self.remote), str(self.other))
        self.command(self.other, "config", "user.name", "Offline Test")
        self.command(self.other, "config", "user.email", "offline@example.invalid")

    def command(self, cwd, *args):
        return subprocess.check_output(["git", *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL).strip()

    def test_reservation_and_receipt_reach_remote_with_unrelated_update_preserved(self):
        (self.other / "unrelated.txt").write_text("Keep this other workflow change\n")
        self.command(self.other, "add", "unrelated.txt")
        self.command(self.other, "commit", "-m", "Unrelated concurrent update")
        self.command(self.other, "push", "origin", "main")
        ledger = {"2026-10-04": {"state": "submitting"}}
        with patch.object(reel, "ROOT", self.work):
            reel.persist([], ledger, "Reserve offline test")
            remote_ledger = json.loads(self.command(self.remote, "show", "main:" + reel.LEDGER_PATH))
            self.assertEqual(remote_ledger["2026-10-04"]["state"], "submitting")
            self.assertEqual((self.work / "unrelated.txt").read_text(), "Keep this other workflow change\n")
            ledger["2026-10-04"].update(state="submitted", buffer_post_id="offline-receipt")
            reel.persist(["2026-10-04"], ledger, "Record offline test receipt")
        self.assertEqual(json.loads(self.command(self.remote, "show", "main:" + reel.HISTORY_PATH)), ["2026-10-04"])
        remote_ledger = json.loads(self.command(self.remote, "show", "main:" + reel.LEDGER_PATH))
        self.assertEqual(remote_ledger["2026-10-04"]["buffer_post_id"], "offline-receipt")

    def test_stale_checkout_refresh_observes_prior_remote_reservation(self):
        (self.other / reel.LEDGER_PATH).write_text(json.dumps({"2026-10-04": {"state": "submitting"}}))
        self.command(self.other, "add", reel.LEDGER_PATH)
        self.command(self.other, "commit", "-m", "Prior run reservation")
        self.command(self.other, "push", "origin", "main")
        with patch.object(reel, "ROOT", self.work):
            self.assertEqual(reel.read_state()[1], {})
            reel.refresh_main()
            self.assertEqual(reel.read_state()[1]["2026-10-04"]["state"], "submitting")


if __name__ == "__main__":
    unittest.main()
