"""Regression checks for paid-call boundaries and uncertain publication outcomes."""
import copy
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("circus_reels", ROOT / "circus/reels/pipeline.py")
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


class ReelsTests(unittest.TestCase):
    def setUp(self):
        self.config = p.load_config()
        self.state = {"jobs": {}, "feed_days": {}, "paid_calls": {}}
        self.script = json.loads((p.HERE / "evergreen.json").read_text())[0]

    def test_bank_passes_and_repeats_are_blocked(self):
        for script in json.loads((p.HERE / "evergreen.json").read_text()):
            fingerprint = p.validate_script(script, self.config, self.state)
            self.state["jobs"][str(len(self.state["jobs"]))] = {"script": script, "script_hash": fingerprint}
            with self.assertRaisesRegex(RuntimeError, "Duplicate"):
                p.validate_script(script, self.config, self.state)

    def test_off_brand_script_is_rejected(self):
        self.script["pillar"] = "politics"
        with self.assertRaisesRegex(RuntimeError, "Off-brand"):
            p.validate_script(self.script, self.config, self.state)

    def test_reserve_exhaustion_never_repeats(self):
        bank = json.loads((p.HERE / "evergreen.json").read_text())
        self.state["jobs"] = {str(i): {"evergreen_index": i} for i in range(len(bank))}
        with self.assertRaisesRegex(RuntimeError, "exhausted"):
            p.choose_evergreen(self.state)

    def test_dst_dates_and_delayed_runs(self):
        for day in ("2026-10-31", "2026-11-01", "2026-03-07", "2026-03-08"):
            cron = p.EVENING_CRON
            now = dt.datetime.fromisoformat(day + "T18:20:00").replace(tzinfo=p.ZONE)
            self.assertTrue(p.schedule_allowed(now, day, cron))
            self.assertTrue(p.schedule_allowed(now.replace(hour=19), day, cron))
            self.assertTrue(p.schedule_allowed(now.replace(hour=23, minute=59), day, cron))
            self.assertFalse(p.schedule_allowed(now.replace(hour=17, minute=59), day, cron))
            self.assertFalse(p.schedule_allowed(now.replace(hour=0), day, cron))
            self.assertFalse(p.schedule_allowed(now, "2020-01-01", cron))
            self.assertFalse(p.schedule_allowed(now, day, "unknown"))

    def test_cron_covers_all_evening_slots_across_dst(self):
        for day in ("2026-03-07", "2026-03-08", "2026-10-31", "2026-11-01"):
            accepted = []
            start = dt.datetime.fromisoformat(day + "T00:00:00+00:00")
            for offset in range(48 * 3):
                now = start + dt.timedelta(minutes=offset * 20)
                if now.hour in (23, 0, 1, 2, 3, 4, 5) and p.schedule_allowed(now, day, p.EVENING_CRON):
                    accepted.append(now.astimezone(p.ZONE))
            self.assertEqual([(x.hour, x.minute) for x in accepted],
                             [(h, m) for h in range(18, 24) for m in (0, 20, 40)])

    def test_rotation_preserves_history_and_never_reuses_uncertain_jobs(self):
        self.config["evergreen_repeat_after_days"] = 90
        bank = json.loads((p.HERE / "evergreen.json").read_text())
        self.state["jobs"] = {
            (dt.date(2026, 1, 1) + dt.timedelta(days=i)).isoformat(): {
                "state": "published", "evergreen_index": i, "script": script,
                "script_hash": p.digest(" ".join(script[k] for k in ("hook", "setup", "punchline")))
            } for i, script in enumerate(bank)}
        before = copy.deepcopy(self.state)
        day = (dt.date(2026, 1, 1) + dt.timedelta(days=len(bank))).isoformat()
        index, script = p.choose_evergreen(self.state, self.config, day)
        self.assertEqual(index, 0)
        p.validate_script(script, self.config, p.evergreen_history(self.state, self.config, day))
        self.assertEqual(self.state, before)
        self.state["jobs"]["2026-01-01"]["state"] = "submitting"
        self.assertNotEqual(p.choose_evergreen(self.state, self.config, day)[0], 0)
        with self.assertRaisesRegex(RuntimeError, "Duplicate"):
            p.validate_script(script, self.config, p.evergreen_history(self.state, self.config, day))

    def test_bank_supports_continuous_daily_rotation_and_scene_durations(self):
        bank = json.loads((p.HERE / "evergreen.json").read_text())
        self.assertGreater(len(bank), self.config["evergreen_repeat_after_days"])
        for script in bank:
            for key in ("hook", "setup", "punchline"):
                self.assertLessEqual(max(3, len(script[key].split()) / 2.6), 13)
        seen = {}
        for n in range(400):
            day = (dt.date(2026, 1, 1) + dt.timedelta(days=n)).isoformat()
            index, script = p.choose_evergreen(self.state, self.config, day)
            if index in seen:
                self.assertGreaterEqual(n - seen[index], 90)
            fingerprint = p.validate_script(script, self.config, p.evergreen_history(self.state, self.config, day))
            self.state["jobs"][day] = {"state": "published", "evergreen_index": index,
                                       "script": script, "script_hash": fingerprint}
            seen[index] = n

    def test_enabled_workflow_keeps_paid_key_absent_and_manual_dispatch_preview_only(self):
        workflow = (ROOT / ".github/workflows/circus-peanuts-reel.yml").read_text()
        self.assertIn(p.EVENING_CRON, workflow)
        self.assertNotIn("vars.CIRCUS_REELS_ENABLED", workflow)
        self.assertNotIn("CIRCUS_OPENAI_API_KEY:", workflow)
        self.assertFalse(self.config["paid_generation_enabled"])
        self.assertEqual(self.config["max_paid_calls_per_day"], 0)
        self.assertTrue(self.config["publishing_enabled"])
        self.assertIn("if: github.event_name == 'schedule'", workflow)
        self.assertIn("if: github.event_name != 'schedule'", workflow)

    def test_free_scheduled_run_skips_rss_paid_calls_and_second_publication(self):
        class Evening(dt.datetime):
            @classmethod
            def now(cls, zone=None):
                return cls(2026, 10, 20, 19, 10, tzinfo=p.ZONE)
        with tempfile.TemporaryDirectory() as tmp:
            event = Path(tmp) / "event.json"
            event.write_text(json.dumps({"schedule": p.EVENING_CRON}))
            def submitted(config, state, day, folder, allowed):
                self.assertTrue(allowed())
                state["jobs"][day]["state"] = "published"
            with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule", "GITHUB_EVENT_PATH": str(event)}), \
                 patch.object(p, "ROOT", Path(tmp)), patch.object(p, "load_state", return_value=self.state), \
                 patch.object(p.dt, "datetime", Evening), patch.object(p, "git", return_value="abc"), \
                 patch.object(p, "persist"), patch.object(p, "render"), patch.object(p, "check_account"), \
                 patch.object(p, "collect_metrics"), patch.object(p, "collect_topics") as feeds, \
                 patch.object(p, "paid_post") as paid, patch.object(p, "generate_assets") as assets, \
                 patch.object(p, "publish", side_effect=submitted) as publish:
                p.run()
                p.run()
                publish.assert_called_once()
                feeds.assert_not_called()
                paid.assert_not_called()
                assets.assert_not_called()

    def test_paid_calls_off_never_contact_provider(self):
        with patch.object(p.requests, "post") as post:
            with self.assertRaisesRegex(RuntimeError, "off"):
                p.paid_post("responses", self.config, self.state, "2026-10-08")
            post.assert_not_called()

    def test_paid_request_reserved_before_timeout_and_no_retry(self):
        self.config.update(paid_generation_enabled=True, max_paid_calls_per_day=1)
        with patch.dict(os.environ, {"CIRCUS_OPENAI_API_KEY": "fake"}), patch.object(p, "persist") as persist:
            def fail(*args, **kwargs):
                self.assertEqual(self.state["paid_calls"]["2026-10-08"], 1)
                persist.assert_called_once()
                raise TimeoutError()
            with patch.object(p.requests, "post", side_effect=fail) as post:
                with self.assertRaises(TimeoutError):
                    p.paid_post("responses", self.config, self.state, "2026-10-08")
                with self.assertRaisesRegex(RuntimeError, "limit reached"):
                    p.paid_post("responses", self.config, self.state, "2026-10-08")
                self.assertEqual(post.call_count, 1)

    def test_failed_durable_reservation_prevents_paid_call(self):
        self.config.update(paid_generation_enabled=True, max_paid_calls_per_day=9)
        with patch.dict(os.environ, {"CIRCUS_OPENAI_API_KEY": "fake"}), patch.object(p, "persist", side_effect=RuntimeError("push failed")), patch.object(p.requests, "post") as post:
            with self.assertRaisesRegex(RuntimeError, "push failed"):
                p.paid_post("responses", self.config, self.state, "2026-10-08")
            post.assert_not_called()

    def test_feed_freshness_and_future_dates(self):
        now = dt.datetime(2026, 10, 8, 12, tzinfo=dt.timezone.utc)
        xml = "<rss><channel>" + "".join(f"<item><title>Dog news</title><link>https://example.org/{i}</link><pubDate>{date}</pubDate></item>" for i, date in enumerate([
            "Thu, 08 Oct 2026 11:00:00 GMT", "Tue, 06 Oct 2026 11:00:00 GMT", "Fri, 09 Oct 2026 11:00:00 GMT", "invalid"])) + "</channel></rss>"
        self.assertEqual(len(p.fresh_feed_items(xml, now)), 1)

    def test_feed_reruns_exclude_today_from_baseline(self):
        current = dt.datetime(2026, 10, 8, 12, tzinfo=dt.timezone.utc)
        xml = "<rss><channel>" + "".join(f"<item><title>Dog story {i}</title><link>https://example.org/{i}</link><pubDate>Thu, 08 Oct 2026 11:00:00 GMT</pubDate></item>" for i in range(4)) + "</channel></rss>"
        self.state["feed_days"] = {"2026-10-07": {"pets": 1}}
        response = type("Response", (), {"content": xml, "raise_for_status": lambda self: None})()
        with patch.object(p.requests, "get", return_value=response):
            first = p.collect_topics(self.config, self.state, current)
            second = p.collect_topics(self.config, self.state, current)
        self.assertEqual(first, second)
        self.assertTrue(all(x["signal"] == "rising feed mentions" for x in first))

    def test_reconciliation_does_not_treat_noon_post_as_reel(self):
        marker = "Circus reel · 2026-10-08"
        self.assertIsNone(p.reconcile([{"id": "noon", "media_product_type": "FEED", "caption": marker}], marker))
        self.assertIsNone(p.reconcile([{"id": "old", "media_product_type": "REELS", "caption": "Circus reel · 2026-10-07"}], marker))
        self.assertEqual(p.reconcile([{"id": "yes", "media_product_type": "REELS", "caption": marker}], marker)["id"], "yes")

    def test_preview_does_not_call_api_or_write_durable_state(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(p, "render", return_value=Path(tmp)/"reel.mp4"), patch.object(p, "persist") as persist, patch.object(p.requests, "get") as get, patch.object(p.requests, "post") as post:
            p.run(preview=True, output=tmp)
            persist.assert_not_called()
            get.assert_not_called()
            post.assert_not_called()

    def test_wrong_account_stops_before_container_creation(self):
        self.config["publishing_enabled"] = True
        with patch.dict(os.environ, {"CIRCUS_IG_ACCESS_TOKEN": "fake", "CIRCUS_IG_USER_ID": "123"}), patch.object(p, "instagram", return_value={"username": "wrong", "user_id": "123"}) as api:
            with self.assertRaisesRegex(RuntimeError, "Wrong Instagram"):
                p.publish(self.config, self.state, "2026-10-08", ROOT, lambda: True)
            self.assertEqual(api.call_count, 1)

    def test_uncertain_publication_is_not_repeated(self):
        day = "2026-10-08"
        folder = ROOT / "docs/circus-reels" / day
        self.config["publishing_enabled"] = True
        self.state["jobs"][day] = {"state": "ready", "marker": "Circus reel · " + day, "media_commit": "abc", "caption": "joke", "container_id": "container"}
        calls = []
        saved = []
        def api(method, path, token, **kwargs):
            calls.append((method, path))
            if path == "me":
                return {"username": "circuspeanutsdaily", "user_id": "123"}
            if path == "123/media":
                return {"data": []}
            if path == "container":
                return {"status_code": "FINISHED"}
            if path == "123/media_publish":
                self.assertEqual(saved[-1]["jobs"][day]["state"], "submitting")
                raise TimeoutError()
            raise AssertionError(path)
        response = type("Response", (), {"ok": True, "content": b"0000ftyp"})()
        with patch.dict(os.environ, {"CIRCUS_IG_ACCESS_TOKEN": "fake", "CIRCUS_IG_USER_ID": "123", "GITHUB_REPOSITORY": "example/test"}), patch.object(p, "instagram", side_effect=api), patch.object(p.requests, "get", return_value=response), patch.object(p, "persist", side_effect=lambda state, *args: saved.append(copy.deepcopy(state))):
            with self.assertRaises(TimeoutError):
                p.publish(self.config, self.state, day, folder, lambda: True)
            with self.assertRaisesRegex(RuntimeError, "no blind retry"):
                p.publish(self.config, self.state, day, folder, lambda: True)
        self.assertEqual(calls.count(("POST", "123/media_publish")), 1)

    def test_disabled_publication_makes_no_requests(self):
        self.config["publishing_enabled"] = False
        with patch.object(p, "instagram") as api:
            p.publish(self.config, self.state, "2026-10-08", ROOT, lambda: True)
            api.assert_not_called()

    def test_uncertain_container_is_blocked_and_can_reconcile_live_reel(self):
        day = "2026-10-08"
        self.config["publishing_enabled"] = True
        self.state["jobs"][day] = {"state": "creating_container", "marker": "Circus reel · " + day}
        rows = []
        def api(method, path, token, **kwargs):
            if path == "me":
                return {"username": "circuspeanutsdaily", "user_id": "123"}
            if path == "123/media":
                return {"data": rows}
            raise AssertionError("No POST expected")
        with patch.dict(os.environ, {"CIRCUS_IG_ACCESS_TOKEN": "fake", "CIRCUS_IG_USER_ID": "123"}), patch.object(p, "instagram", side_effect=api), patch.object(p, "persist"):
            with self.assertRaisesRegex(RuntimeError, "no blind retry"):
                p.publish(self.config, self.state, day, ROOT, lambda: True)
            rows.append({"id": "live", "caption": "Circus reel · " + day, "media_product_type": "REELS", "permalink": "https://example.invalid/live"})
            p.publish(self.config, self.state, day, ROOT, lambda: True)
        self.assertEqual(self.state["jobs"][day]["media_id"], "live")

    def test_missing_insights_are_not_recorded_as_zero(self):
        self.state["jobs"]["2026-10-07"] = {"state": "published", "media_id": "live"}
        def api(method, path, token, **kwargs):
            if path == "me":
                return {"username": "circuspeanutsdaily", "user_id": "123"}
            if kwargs["params"]["metric"] == "views":
                return {"data": [{"values": [{"value": 12}]}]}
            raise RuntimeError("Permission missing")
        with patch.dict(os.environ, {"CIRCUS_IG_ACCESS_TOKEN": "fake", "CIRCUS_IG_USER_ID": "123"}), patch.object(p, "instagram", side_effect=api), patch.object(p, "persist"):
            p.collect_metrics(self.state, dt.datetime(2026, 10, 8, 18, tzinfo=p.ZONE))
        snapshot = self.state["jobs"]["2026-10-07"]["metrics"]["24h"]
        self.assertEqual(snapshot["views"], 12)
        self.assertNotIn("reach", snapshot)
        self.assertIn("reach", snapshot["unavailable"])


if __name__ == "__main__":
    unittest.main()
